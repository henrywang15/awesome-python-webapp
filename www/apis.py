#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'

import json, logging
from functools import wraps
from web import ctx


def dumps(obj):
    return json.dumps(obj)


class APIError(Exception):
    """
    the base APIError which contains error(required),data(optional) and message(optional)
    """

    def __init__(self, error, data='', message=''):
        self.error = error
        self.data = data
        self.message = message
        super(APIError, self).__init__()


class APIValueError(APIError):
    def __init__(self, field, message=''):
        super(APIValueError, self).__init__('value:invalid', field, message)


class APIResourceNotFoundError(APIError):
    def __init__(self, field, message=''):
        super(APIResourceNotFoundError, self).__init__('value:notfound', field, message)


class APIPermissionError(APIError):
    def __init__(self, message=''):
        super(APIPermissionError, self).__init__('permission:forbidden', 'permission', message)


def api(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            r = dumps(func(*args, **kwargs))
        except APIError as e:
            r = json.dumps(dict(error=e.error, data=e.data, message=e.message))
        except Exception as e:
            logging.exception(e)
            r = json.dumps(dict(error='internalerror', data=e.__class__.__name__, message=''))
        ctx.response.content_type = 'application/json'
        return r
    return wrapper


