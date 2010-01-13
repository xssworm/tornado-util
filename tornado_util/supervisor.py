#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
This is module for creating of init.d scripts for tornado-based
services

It implements following commands:
* start
* stop
* restart
* status

Sample usage:

=== /etc/init.d/frontik ===
#!/usr/bin/python
# -*- coding: utf-8 -*-

from tornado_util.supervisor import supervisor

supervisor(
    script='/usr/bin/frontik_srv.py',
    config='/etc/frontik/frontik.cfg'
)
'''

import sys
import urllib2
import httplib
import logging
import subprocess

from functools import partial

import tornado.options
from tornado.options import options

def is_running(port):
    try:
        urllib2.urlopen('http://localhost:%s/status/' % (port,))
        return True
    except urllib2.URLError:
        return False
    except urllib2.HTTPError:
        return False

def start_worker(script, port):
    logging.debug('start worker %s', port)

    args = [script, 
            '--port=%s' % (port,)]

    if options.logfile_template:
        args.append('--logfile=%s' % (options.logfile_template % dict(port=port),))

    if options.pidfile_template:
        args.append('--pidfile=%s' % (options.pidfile_template % dict(port=port),))
    
    return subprocess.Popen(args)

def stop_worker(port):
    logging.debug('stop worker %s', port)
    try:
        urllib2.urlopen('http://localhost:%s/stop/' % (port,))
    except urllib2.URLError:
        pass
    except httplib.BadStatusLine:
        pass

def map_workers(f):
    return map(f, [options.start_port + p for p in range(options.workers_count)])

def stop():
    if any(map_workers(is_running)):
        for i in range(3):
            logging.warning('some of the workers are running; trying to kill')
            map_workers(stop_worker)

            if not all(map_workers(is_running)):
                break
        else:
            logging.warning('failed to stop workers')
            sys.exit(1)

def start(script):
    map_workers(partial(start_worker, script))

def status():
    res = map_workers(is_running)
    if all(res):
        logging.info('all workers are running')
    elif any(res):
        logging.warn('some workers are running!')
    else:
        logging.info('all workers are stopped')

def supervisor(script, config):
    tornado.options.define('start_port', 8000, int)
    tornado.options.define('workers_count', 4, int)
    tornado.options.define('logfile_template', None, str)
    tornado.options.define('pidfile_template', None, str)

    tornado.options.parse_config_file(config)

    (cmd,) = tornado.options.parse_command_line()

    logging.getLogger().setLevel(logging.DEBUG)
    tornado.options.enable_pretty_logging()

    if cmd == 'start':
        stop()
        start(script)

    elif cmd == 'stop':
        stop()

    elif cmd == 'restart':
        stop()
        start(script)

    elif cmd == 'status':
        status()

    else:
        logging.error('either --start or --stop should be present')
        sys.exit(1)
