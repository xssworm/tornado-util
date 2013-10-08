# -*- coding: utf-8 -*-

"""
Example usage:

if __name__ == '__main__':
    # read configs and process standard options
    tornado_util.server.bootstrap(config_filename)

    tornado_util.server.main(tornado.web.Application(...))
"""

import time
import logging

import tornado.web
import tornado.options
import tornado.autoreload
from tornado.options import options

log = logging.getLogger('tornado_util.server')

tornado.options.define('stop_timeout', 3, int)


def bootstrap(config_file, default_port=8080):
    """
    - define options: config, host, port, daemonize, autoreload
    - read command line options and config file
    - daemonize
    """

    tornado.options.define('config', None, str)
    tornado.options.define('host', '0.0.0.0', str)
    tornado.options.define('port', default_port, int)
    tornado.options.define('daemonize', False, bool)
    tornado.options.define('autoreload', True, bool)
    tornado.options.define('log_blocked_ioloop_timeout', 0, float)
    tornado.options.parse_command_line()

    if options.config:
        config_to_read = options.config
    else:
        config_to_read = config_file

    tornado.options.parse_config_file(config_to_read)

    # override options from config with command line options
    tornado.options.parse_command_line()

    if options.daemonize:
        import daemon
        ctx = daemon.DaemonContext()
        ctx.open()

    tornado.options.process_options()

    log.debug('read config: %s', config_to_read)
    tornado.autoreload.watch_file(config_to_read)


def main(app, on_stop_request=lambda: None, on_ioloop_stop=lambda: None):
    """
    - run server on host:port
    - launch autoreload on file changes
    """

    import tornado.httpserver
    import tornado.ioloop
    import tornado.web

    try:
        log.info('starting server on %s:%s', options.host, options.port)
        http_server = tornado.httpserver.HTTPServer(app)
        http_server.listen(options.port, options.host)
    
        io_loop = tornado.ioloop.IOLoop.instance()
        if tornado.options.options.log_blocked_ioloop_timeout > 0:
            io_loop.set_blocking_log_threshold(tornado.options.options.log_blocked_ioloop_timeout)

        if options.autoreload:
            import tornado.autoreload
            tornado.autoreload.start(io_loop, 1000)

        def stop_handler(signum, frame):
            log.info('requested shutdown')
            log.info('shutdowning server on %s:%s', options.host, options.port)
            http_server.stop()

            if tornado.ioloop.IOLoop.instance().running():
                log.info('going down in %s sec', options.stop_timeout)

                def timeo_stop():
                    if tornado.ioloop.IOLoop.instance().running():
                        log.info('stopping ioloop')
                        tornado.ioloop.IOLoop.instance().stop()
                        log.info('stopped')
                        on_ioloop_stop()

                def add_timeo():
                    tornado.ioloop.IOLoop.instance().add_timeout(time.time()+options.stop_timeout, timeo_stop)

                tornado.ioloop.IOLoop.instance().add_callback(add_timeo)

            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            on_stop_request()

        import signal
        signal.signal(signal.SIGTERM, stop_handler)

        io_loop.start()
    except Exception, e:
        log.exception('failed to start Tornado application')
