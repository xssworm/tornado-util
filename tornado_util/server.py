# -*- coding: utf-8 -*-

'''
Sample usage from some-day-to-be-open-sourced "frontik" application server:
### frontik_srv.py
# ...
if __name__ == '__main__':
    config_filename = ...

    # define additional options
    tornado.options.define('suppressed_loggers', ['tornado.httpclient'], list)


    # read configs and process standard options
    tornado_util.server.bootstrap(config_filename)


    # some pre-main-loop logic
    for log_channel_name in options.suppressed_loggers:
        logging.getLogger(log_channel_name).setLevel(logging.WARN)


    # enter the main loop
    import frontik.app
    tornado_util.server.main(frontik.app.get_app())

'''
import time
from functools import partial

import logging
log = logging.getLogger('tornado_util.server')

import tornado.web
import tornado.options
import tornado.autoreload
from tornado.options import options

tornado.options.define('stop_timeout', 3, int)

def bootstrap(config_file, default_port=8080):
    '''
    - объявить стандартные опции config, host, port, daemonize, autoreload
    - прочитать командную строку, конфигурационный файл
    - демонизироваться
    - инициализировать протоколирование
    '''

    import sys
    import os.path

    tornado.options.define('config', None, str)

    tornado.options.define('host', '0.0.0.0', str)
    tornado.options.define('port', default_port, int)
    tornado.options.define('daemonize', True, bool)
    tornado.options.define('autoreload', True, bool)
    tornado.options.define('log_blocked_ioloop_timeout', 0, float)
    tornado.options.parse_command_line()

    if options.config:
        config_to_read = options.config
    else:
        config_to_read = config_file

    tornado.options.parse_config_file(config_to_read)

    tornado.options.parse_command_line()

    if options.daemonize:
        import daemon

        ctx = daemon.DaemonContext()
        ctx.open()

    tornado.options.process_options()

    log.debug('read config: %s', config_to_read)
    tornado.autoreload.watch_file(config_to_read)

def main(app, on_stop_request = lambda: None, on_ioloop_stop = lambda: None):
    '''
    - запустить веб-сервер на указанных в параметрах host:port
    - запустить автоперезагрузку сервера, при изменении исходников
    '''

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
            log.info('Requested shutdown')
            log.info('Shutdowning server on %s:%s', options.host, options.port)
            http_server.stop()

            if tornado.ioloop.IOLoop.instance().running():
                log.info('Going down in %s s.', options.stop_timeout)

                def timeo_stop():
                    if tornado.ioloop.IOLoop.instance().running():
                        log.info('Stoping ioloop.')
                        tornado.ioloop.IOLoop.instance().stop()
                        log.info('Stoped.')
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
        log.exception('main failed')

class StatusHandler(tornado.web.RequestHandler):
    def get(self, *args, **kw):
        self.write('Ok\n')

status_handler = ('/status/', StatusHandler)
