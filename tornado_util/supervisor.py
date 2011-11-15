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
import signal

import sys
import urllib2
import httplib
import logging
import subprocess
import time

from functools import partial

import tornado.options
import tornado_util.server
from tornado.options import options

tornado.options.define('port', 8000, int)
tornado.options.define('workers_count', 4, int)
tornado.options.define('logfile_template', None, str)
tornado.options.define('pidfile_template', None, str)

tornado.options.define('start_check_timeout', 3, int)


import os.path
import os

def is_running(port):
    try:
        urllib2.urlopen('http://localhost:%s/status/' % (port,))
        return True
    except urllib2.URLError:
        return False
    except urllib2.HTTPError:
        return False

def start_worker(script, config, port):
    logging.debug('start worker %s', port)

    args = [script,
            '--config=%s' % (config,),
            '--port=%s' % (port,)]

    if options.logfile_template:
        args.append('--logfile=%s' % (options.logfile_template % dict(port=port),))

    args.append('--pidfile=%s' % (options.pidfile_template % dict(port=port),))

    return subprocess.Popen(args)

def stop_worker(port):
    logging.debug('stop worker %s', port)
    path = options.pidfile_template % dict(port=port)
    if not os.path.exists(path):
        logging.warning('pidfile %s does not exist. dont know how to stop', path)
    try:
        pid = int(file(path).read())
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    except IOError:
        pass
    except ValueError:
        pass

def rm_pidfile(port):
    path = options.pidfile_template % dict(port=port)
    if os.path.exists(path):
        try:
            os.remove(path)
        except :
            logging.warning('failed to rm pidfile %s', path)

def map_workers(f):
    return map(f, [options.port + p for p in range(options.workers_count)])

def stop():
    if any(map_workers(is_running)):
        logging.warning('some of the workers are running; trying to kill')

    for i in xrange(3):
        map_workers(stop_worker)
        time.sleep(options.stop_timeout/3.)
        if not any(map_workers(is_running)):
            map_workers(rm_pidfile)
            break
    else:
        logging.warning('failed to stop workers')
        sys.exit(1)

def start(script, config):
    map_workers(partial(start_worker, script, config))
    time.sleep(options.start_check_timeout)

def status(expect=None):
    res = map_workers(is_running)

    if all(res):
        if expect == 'stopped':
            logging.error('all workers are running')
            return 1
        else:
            logging.info('all workers are running')
            return 0
    elif any(res):
        logging.warn('some workers are running!')
        return 1
    else:
        if expect == 'started':
            logging.error('all workers are stopped')
            return 1
        else:
            logging.info('all workers are stopped')
            return 0

def supervisor(script, config):
    tornado.options.parse_config_file(config)

    (cmd,) = tornado.options.parse_command_line()

    logging.getLogger().setLevel(logging.DEBUG)
    tornado.options.enable_pretty_logging()

    if cmd == 'start' or cmd == 'restart':
        stop()
        start(script, config)
        sys.exit(status(expect='started'))

    elif cmd == 'stop':
        stop()
        sys.exit(status(expect='stopped'))

    elif cmd == 'status':
        status()

    else:
        logging.error('either --start, --stop, --restart or --status should be present')
        sys.exit(1)
