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

import logging
log = logging.getLogger('tornado_util.server')

import tornado.web
import tornado.options
from tornado.options import options

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

    tornado.options.parse_command_line()
    if options.config:
        configs_to_read = [options.config]
    else:
        configs_to_read = [config_file]

    configs = tornado.options.parse_config_files(configs_to_read)
    
    tornado.options.parse_command_line()

    if options.daemonize:
        import daemon

        ctx = daemon.DaemonContext()
        ctx.open()

    tornado.options.process_options()

    if configs:
        log.debug('read configs: %s', ', '.join(os.path.abspath(i) for i in configs))
    else:
        sys.stderr.write('failed to find any config file, aborting\n')
        sys.exit(1)

def main(app, watch_paths=[]):
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
    
        if options.autoreload:
            import tornado.autoreload
            tornado.autoreload.start(io_loop, 1000, watch_paths)

        io_loop.start()
    except Exception, e:
        log.exception('main failed')

class StatusHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('Ok\n')

status_handler = ('/status/', StatusHandler)

class StopHandler(tornado.web.RequestHandler):
    def get(self):
        log.info('requested shutdown')
        tornado.ioloop.IOLoop.instance().stop()

stop_handler = ('/stop/', StopHandler)
