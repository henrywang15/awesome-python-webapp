#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'

import cgi
from nameddict import Nameddict
import urllib.parse
from http_data import *
import datetime
from utc import UTC
import threading
import os, mimetypes, logging, sys
import types
import traceback
from io import StringIO
from functools import wraps
from types import GeneratorType

ctx = threading.local()

UTC_ZERO = UTC('+00:00')


def _quote(s):
    return urllib.parse.quote(s)


def _unquote(s):
    return urllib.parse.unquote(s)


class HttpError(Exception):
    def __init__(self, code):
        super(HttpError, self).__init__()
        self.status = '{} {}'.format(code, RESPONSE_STATUSES[code])

    def header(self, name, value):
        if not hasattr(self, '_headers'):
            self._headers = [HEADER_X_POWERED_BY]
        self._headers.append((name, value))

    headers = property(lambda self: self._headers if hasattr(self, '_headers') else [])

    def __str__(self):
        return self.status

    __repr__ = __str__


class RedirectError(HttpError):
    def __init__(self, code, location):
        super(RedirectError, self).__init__(code)
        self.location = location

    def __str__(self):
        return '{}, {}'.format(self.status, self.location)

    __repr__ = __str__


def badrequest():
    return HttpError(400)


def unauthorized():
    return HttpError(401)


def forbidden():
    return HttpError(403)


def notfound():
    return HttpError(404)


def conflict():
    return HttpError(409)


def internalerror():
    return HttpError(500)


def redirect(location):
    return RedirectError(301, location)


def found(location):
    return RedirectError(302, location)


def seeother(location):
    return RedirectError(303, location)


def get(path):
    def decorator(func):
        func.__web_route__ = path
        func.__web_method__ = 'GET'
        return func
    return decorator


def post(path):
    def decorator(func):
        func.__web_route__ = path
        func.__web_method__ = 'GET'
        return func
    return decorator


_re_route = re.compile(r'(:[a-zA-Z_]\w*)')


def _build_regex(path):
    re_list = ['^']
    var_list = []
    is_var = False
    for v in _re_route.split(path):
        if is_var:
            var_name = v[1:]
            var_list.append(var_name)
            re_list.append(r'(?P<{}>[^/]+)'.format(var_name))

        else:
            # s=''
            # for ch in v:
            # if re.compile(r'[a-zA-Z0-9]').match(ch):
            # s+=ch
            # else:
            # s=s+''+'\\'+ch
            re_list.append(v)
        is_var = not is_var
    re_list.append('$')
    return ''.join(re_list)


class Route:
    def __init__(self, func):
        self.path = func.__web_route__
        self.method = func.__web_method__
        self.is_static = _re_route.search(self.path) is None
        if not self.is_static:
            self.route = re.compile(_build_regex(self.path))
        self.func = func

    def match(self, url):
        m = self.route.search(url)
        if m:
            return m.groups()
        return None

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def __str__(self):
        if self.is_static:
            return 'Route(static,{},path={})'.format(self.method, self.path)
        return 'Route(dynamic,{},path={})'.format(self.method, self.path)

    __repr__ = __str__


def _static_file_generator(fpath):
    block_size = 8192
    with open(fpath, 'rb') as f:
        block = f.read(block_size)
        while block:
            yield block
            block = f.read(block_size)


class StaticFileRoute:
    def __init__(self):
        self.method = 'GET'
        self.is_static = False
        self.route = re.compile(r'^/static/(.+)$')

    def match(self, url):
        if url.startswith('/static/'):
            return url[1:],
        return None

    def __call__(self, *args, **kwargs):
        fpath = os.path.join(ctx.application.document_root, args[0])
        if not os.path.isfile(fpath):
            raise notfound()
        fext = os.path.splitext(fpath)[1]
        ctx.response.content_type = mimetypes.types_map.get(fext.lower(), 'application/octet-stream')
        return _static_file_generator(fpath)


class Request:
    """
    Request Object for obtaining all http request information
    """

    def __init__(self, environ):
        self._environ = environ

    def _parse_input(self):
        params = cgi.FieldStorage(fp=self._environ['wsgi.input'], environ=self._environ, keep_blank_values=1)
        return {key: params[key] for key in params}

    def _get_raw_input(self):
        if not hasattr(self, '_raw_input'):
            self._raw_input = self._parse_input()
        return self._raw_input

    def __getitem__(self, key):
        r = self._get_raw_input()[key]
        if isinstance(r, list):
            return r[0]
        return r

    def get(self, key, default=None):
        r = self._get_raw_input().get(key, default)
        if isinstance(r, list):
            return r[0]
        return r

    def gets(self, key):
        r = self._get_raw_input()[key]
        return r if isinstance(r, list) else [r]

    def input(self, **kwargs):
        kwargs = Nameddict(**kwargs)
        for k, v in self._get_raw_input():
            kwargs[k] = v[0] if isinstance(v, list) else v
        return kwargs

    def get_body(self):
        fp = self._environ['wsgi.input']
        fp.seek(0)
        return fp.read()

    def _get_headers(self):
        if not hasattr(self, '_headers'):
            headers = {}
            for k, v in self._environ.items():
                if k.startswith('HTTP_'):
                    headers[k[5:].replace('_', '-').upper()] = v
            self._headers = headers
        return self._headers

    def _get_cookies(self):
        if not hasattr(self, '_cookies'):
            cookies = {}
            cookie_str = self._environ.get('HTTP_COOKIE')
            if cookie_str:
                for c in cookie_str.split(';'):
                    pos = c.find('=')
                    if pos > 0:
                        cookies[c[:pos].strip()] = _unquote(c[pos + 1:])
            self._cookies = cookies
        return self._cookies

    document_root = property(lambda self: self._environ.get('document_root'.upper(), ''))
    query_string = property(lambda self: self._environ.get('query_string'.upper(), ''))
    environ = property(lambda self: self._environ)
    request_method = property(lambda self: self._environ['request_method'.upper()])
    path_info = property(lambda self: _unquote(self._environ.get('path_info'.upper(), '')))
    http_host = property(lambda self: self._environ.get('http_host'.upper(), ''))
    headers = property(lambda self: Nameddict(**self._get_headers().read))
    header = property(lambda self, header, default=None: self._get_headers.get(header.upper(), default))
    cookies = property(lambda self: Nameddict(**self._get_cookies()))
    cookie = property(lambda self, name, default=None: self._get_cookies().get(name, default))


class Response:
    def __init__(self):
        self._status = '200 OK'
        self._headers = {'CONTENT-TYPE': 'text/html; charset=utf-8'}

    @property
    def headers(self):
        L = [(RESPONSE_HEADERS_DICT.get(k, k), v) for k, v in self._headers.items()]
        if hasattr(self, '_cookies'):
            for v in self._cookies.values():
                L.append(('Set-Cookie', v))
        L.append(HEADER_X_POWERED_BY)
        return L

    def header(self, name):
        key = name.upper()
        if key not in RESPONSE_HEADERS_DICT:
            key = name
        return self._headers.get(key)

    def unset_header(self, name):
        key = name.upper()
        if key not in RESPONSE_HEADERS_DICT:
            key = name
        if key in self._headers:
            del self._headers[key]

    def set_header(self, name, value):
        key = name.upper()
        if key not in RESPONSE_HEADERS_DICT:
            key = name
        self._headers[key] = value

    def delete_cookie(self, name):
        self.set_cookie(name, '__deleted__', expires=0)

    def set_cookie(self, name, value, max_age=None, expires=None, path='/', domain=None, secure=False, http_only=True):
        if not hasattr(self, '_cookies'):
            self._cookies = {}
        L = ['{}={}'.format(_quote(name), _quote(value))]
        if expires is not None:
            if isinstance(expires, int):
                L.append('Expires={}'.format(datetime.datetime.fromtimestamp(expires, UTC_ZERO)).
                         strftime('%a, %d-%b-%Y %H:%M:%S GMT'))
            if isinstance(expires, (datetime.datetime, datetime.date)):
                L.append('Expires={}'.format(expires.astimezone(UTC_ZERO)).
                         strftime('%a, %d-%b-%Y %H:%M:%S GMT'))
        elif isinstance(max_age, int):
            L.append('Max-age={}'.format(max_age))
        L.append('Path={}'.format(path))
        if domain:
            L.append('Domain={}'.format(domain))
        if secure:
            L.append('Secure')
        if http_only:
            L.append('HttpOnly')
        self._cookies[name] = '; '.join(L)

    def unset_cookie(self, name):
        if hasattr(self, '_cookies'):
            if name in self._cookies:
                del self._cookies[name]

    @property
    def content_type(self):
        return self.header('CONTENT-TYPE')

    @content_type.setter
    def content_type(self, value):
        self.set_header('CONTENT-TYPE', value) if value else self.unset_header('CONTENT-TYPE')

    @property
    def content_length(self):
        return self.header('CONTENT-LENGTH')

    @content_length.setter
    def content_length(self, value):
        self.set_header('CONTENT-LENGTH', str(value)) if value else self.unset_header('CONTENT-LENGTH')

    status_code = property(lambda self: int(self._status[:3]))

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        if isinstance(value, int):
            if 100 <= value <= 599:
                st = RESPONSE_STATUSES.get(value, '')
                if st:
                    self._status = '{} {}'.format(value, st)
                else:
                    self._status = str(value)
        elif isinstance(value, str):
            if RE_RESPONSE_STATUS.search(value):
                self._status = value
            else:
                raise ValueError('bad response status {}'.format(value))
        else:
            raise TypeError('bad type of response status')


class Template:
    def __init__(self, template_name, **kwargs):
        self.template_name = template_name
        self.model = dict(**kwargs)


class TemplateEngine:
    def __call__(self, path, model):
        return '<!-- override this method to render template -->'


class Jinja2TemplateEngine(TemplateEngine):
    def __init__(self, template_dir, **kwargs):
        from jinja2 import Environment, FileSystemLoader
        if 'autoescape' not in kwargs:
            kwargs['autoescape'] = True
        self._env = Environment(loader=FileSystemLoader(template_dir), **kwargs)

    def add_filter(self, name, fn_filter):
        self._env.filters[name] = fn_filter

    def __call__(self, path, model):
        return self._env.get_template(path).render(**model)


def _default_error_handler(e, start_response):
    if isinstance(e, HttpError):
        logging.info('HttpError {}'.format(e.status))
        e.header('Content-Type', 'text/html')
        start_response(e.status, e.headers)
        return '<html><body><h1>%s</h1></body></html>'.format(e.status).encode('utf8')
    logging.exception('Exception')
    internal = internalerror()
    internal.header('Content-Type', 'text/html')
    start_response(internal.status, internal.headers)
    return '<html><body><h1>500 Internal Server Error</h1><h3>{!s}</h3></body></html>'.format(internal).encode('utf8')


def view(path):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            r = func(*args, **kwargs)
            if isinstance(r, dict):
                logging.info('return Template')
                return Template(path, **r)
            raise ValueError('Expected return a dict when using @view decorator')

        return wrapper

    return decorator


RE_INTERCEPTOR_STARTS_WITH = re.compile(r'^([^\*\?]+)\*?$')
RE_INTERCEPTOR_ENDS_WITH = re.compile(r'^\*([^\*\?]+)$')


def _build_pattern_fn(pattern):
    m = RE_INTERCEPTOR_STARTS_WITH.search(pattern)
    if m:
        return lambda p: p.startswith(m.group(1))
    m = RE_INTERCEPTOR_ENDS_WITH.search(pattern)
    if m:
        return lambda p: p.endswith(m.group(1))
    raise ValueError('invalid pattern definition in interceptor')


def interceptor(pattern='/'):
    def decorator(func):
        func.__interceptor__ = _build_pattern_fn(pattern)
        return func

    return decorator


def _build_interceptor_fn(func, next):
    def wrapper():
        if func.__interceptor__(ctx.request.path_info):
            return func(next)
        else:
            return next()

    return wrapper


def _build_interceptor_chain(last_fn, *interceptors):
    L = list(interceptors)
    L.reverse()
    fn = last_fn
    for f in L:
        fn = _build_interceptor_fn(f, fn)
    return fn


def _load_module(module_name):
    last_dot = module_name.rfind('.')
    if last_dot == -1:
        return __import__(module_name, globals(), locals())
    from_module = module_name[:last_dot]
    import_module = module_name[last_dot + 1:]
    m = __import__(from_module, globals(), locals(), [import_module])
    return getattr(m, import_module)


class WSGIApplication:
    def __init__(self, document_root=None, **kwargs):
        """
        :param document_root: document root path
        :param kwargs:
        """

        self._running = False
        self._document_root = document_root

        self._interceptors = []
        self._template_engine = None

        self._get_static = {}
        self._post_static = {}

        self._get_dynamic = []
        self._post_dynamic = []

    def _check_out_running(self):
        if self._running:
            raise RuntimeError('Cannot modify WSGIApplication when running')

    @property
    def template_engine(self):
        return self._template_engine

    @template_engine.setter
    def template_engine(self, engine):
        self._check_out_running()
        self._template_engine = engine

    def add_module(self, mod):
        self._check_out_running()
        m = mod if type(mod) == types.ModuleType else _load_module(mod)
        logging.info('add module:{}'.format(m.__name__))
        for name in dir(m):
            fn = getattr(m, name)
            if callable(fn) and hasattr(fn, '__web_route__') and hasattr(fn, '__web_method__'):
                self.add_url(fn)

    def add_url(self,func):
        self._check_out_running()
        route=Route(func)
        if route.is_static:
            if route.method=='GET':
                self._get_static[route.path]=route
            if route.method=='POST':
                self._post_static[route.path]=route
        else:
            if route.method=='GET':
                self._get_dynamic.append(route)
            if route.method=='POST':
                self._post_dynamic.append(route)
        logging.info('add route: {!s}'.format(route))

    def add_interceptor(self, func):
        self._check_out_running()
        self._interceptors.append(func)
        logging.info('add interceptor: {!s}'.format(func))

    def run(self, port=9000, host='127.0.0.1'):
        from wsgiref.simple_server import make_server

        logging.info('application {} will start at {}:{}'.format(self._document_root, host, port))
        server = make_server(host, port, self.get_wsgi_application(debug=True))
        server.serve_forever()

    def get_wsgi_application(self, debug=False):
        self._check_out_running()
        if debug:
            self._get_dynamic.append(StaticFileRoute())
        self._running = True
        _application = Nameddict(document_root=self._document_root)

        def fn_route():
            request_method = ctx.request.request_method
            path_info = ctx.request.path_info
            if request_method == 'GET':
                fn = self._get_static.get(path_info, None)
                if fn:
                    return fn()
                for fn in self._get_dynamic:
                    args = fn.match(path_info)
                    if args:
                        return fn(*args)
                raise notfound()
            if request_method == 'POST':
                fn = self._post_static.get(path_info, None)
                if fn:
                    return fn()
                for fn in self._post_dynamic:
                    args = fn.match(path_info)
                    if args:
                        return fn(*args)
                raise notfound()
            raise badrequest()

        fn_exec = _build_interceptor_chain(fn_route, *self._interceptors)

        def wsgi(environ, start_response):
            ctx.application = _application
            ctx.request = Request(environ)
            response = ctx.response = Response()
            try:
                r = fn_exec()
                start_response(response.status, response.headers)
                if isinstance(r, Template):
                    r = self._template_engine(r.template_name, r.model)
                    yield r.encode('utf8')
                elif isinstance(r,GeneratorType):
                    for subr in r:
                        yield subr
            except RedirectError as e:
                response.set_header('Location', e.location)
                start_response(e.status, response.headers)
            except HttpError as e:
                response.set_header('Content-type','text/plain')
                start_response(e.status, response.headers)
                yield b'Not Found'
                # return ['<html><body><h1>{}</h1></body></html>'.format(e.status).encode('utf8')]
            except Exception as e:
                logging.exception(e)
                if not debug:
                    start_response('500 Internal Server Error', [])
                    return [b'<html><body><h1>500 Internal Server Error</h1></body></html>']
                exc_type, exc_value, exc_traceback = sys.exc_info()
                fp = StringIO()
                traceback.print_exception(exc_type, exc_value, exc_traceback, file=fp)
                stacks = fp.getvalue()
                fp.close()
                start_response('500 Internal Server Error', [])
                return [
                    b'<html><body><h1>500 Internal Server Error</h1><div style="font-family:Monaco, Menlo, \
                    Consolas,\'Courier New\', monospace;"><pre>',
                    _quote(stacks).encode('utf8'),
                    b'</pre></div></body></html>']
            finally:
                del ctx.application
                del ctx.request
                del ctx.response

        return wsgi






















