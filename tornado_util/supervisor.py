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
import glob
import re

from functools import partial

import tornado.options
import tornado_util.server
from tornado.options import options

tornado.options.define('port', 8000, int)
tornado.options.define('workers_count', 4, int)
tornado.options.define('logfile_template', None, str)
tornado.options.define('pidfile_template', None, str)

tornado.options.define('start_check_timeout', 3, int)
tornado.options.define('supervisor_sigterm_timeout', 4, int)


import os.path
import os


def is_alive(port):
    try:
        path = options.pidfile_template % dict(port=port)
        pid = int(file(path).read())
        if os.path.exists("/proc/{0}".format(pid)):
            return True
        return False
    except Exception:
        return False


def is_running(port):
    try:
        urllib2.urlopen('http://localhost:%s/status/' % (port,))
        return True
    except urllib2.URLError:
        return False
    except urllib2.HTTPError:
        return False

def start_worker(script, config, port):
    if is_alive(port):
        logging.warn("another process already started on %s", port)
        return None
    logging.debug('start worker %s', port)

    args = [script,
            '--config=%s' % (config,),
            '--port=%s' % (port,),
            '--pidfile=%s' % (options.pidfile_template % dict(port=port),)]

    if options.logfile_template:
        args.append('--logfile=%s' % (options.logfile_template % dict(port=port),))

    return subprocess.Popen(args)

def stop_worker(port, signal_to_send=signal.SIGTERM):
    logging.debug('stop worker %s', port)
    path = options.pidfile_template % dict(port=port)
    if not os.path.exists(path):
        logging.warning('pidfile %s does not exist. dont know how to stop', path)
    try:
        pid = int(file(path).read())
        os.kill(pid, signal_to_send)
    except OSError:
        pass
    except IOError:
        pass
    except ValueError:
        pass

def rm_pidfile(port):
    pid_path = options.pidfile_template % dict(port=port)
    if os.path.exists(pid_path):
        try:
            os.remove(pid_path)
        except :
            logging.warning('failed to rm  %s', pid_path)

def map_workers(f):
    return map(f, [options.port + p for p in range(options.workers_count)])

def map_stale_workers(f):
    ports = [str(options.port + p) for p in range(options.workers_count)]
    stale_ports = []

    if options.pidfile_template.find('%(port)s') > -1:
        parts = options.pidfile_template.partition('%(port)s')
        re_escaped_template = ''.join([re.escape(parts[0]), '([0-9]+)', re.escape(parts[-1])])
        # extract ports from pid file names and add them to stale_ports if they are not in ports from settings
        for pidfile in glob.glob(options.pidfile_template % dict(port="*")):
            port_match = re.search(re_escaped_template, pidfile)
            if port_match and not port_match.group(1) in ports:
                stale_ports.append(port_match.group(1))
    return map(f, stale_ports)

def map_all_workers(f):
    return map_workers(f) + map_stale_workers(f)

def stop():
    if any(map_all_workers(is_running)):
        logging.warning('some of the workers are running; trying to kill')

    map_all_workers(lambda port: stop_worker(port, signal.SIGTERM))
    time.sleep(int(options.supervisor_sigterm_timeout))
    map_all_workers(lambda port: stop_worker(port, signal.SIGKILL) if is_alive(port) else rm_pidfile(port))
    time.sleep(1)
    map_all_workers(lambda port:
                    rm_pidfile(port) if not is_alive(port)
                    else logging.warning("failed to stop worker on port %d" % port))
    if any(map_all_workers(is_alive)):
        logging.warning('failed to stop workers')
        sys.exit(1)

def start(script, config):
    map_workers(partial(start_worker, script, config))
    time.sleep(options.start_check_timeout)

def status(expect=None):
    res = map_stale_workers(is_running)
    if any(res):
        logging.warn('some stale workers are running!')

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

    if cmd == 'start':
        start(script, config)
        sys.exit(status(expect='started'))

    if cmd == 'restart':
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
