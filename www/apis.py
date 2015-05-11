#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'

import json, logging
from functools import wraps
from web import ctx

def _dump(obj):
    if isinstance(obj, Page):
        return {
            'page_index': obj.page_index,
            'page_count': obj.page_count,
            'item_count': obj.item_count,
            'has_next': obj.has_next,
            'has_previous': obj.has_previous
        }
    raise TypeError('%s is not JSON serializable' % obj)


def dumps(obj):
    return json.dumps(obj, default=_dump)


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


class Page:
    def __init__(self,item_count,page_index=1,page_size=10):
        self.item_count=item_count
        self.page_size=page_size
        self.page_count=item_count // page_size + (1 if item_count % page_size >0 else 0)
        if item_count ==0 or page_index <1 or page_index > self.page_count:
            self.offset=0
            self.limit=0
            self.page_index=1
        else:
            self.page_index=page_index
            self.offset=self.page_size*(page_index-1)
            self.limit=self.page_size
        self.has_next= self.page_index<self.page_count
        self.has_previous=self.page_index >1

    def __str__(self):
        return 'item_count:{},page_size:{},page_count:{},page_index:{},offset:{},limit:{}'.format(
            self.item_count,self.page_size,self.page_count,self.page_index,self.offset,self.limit
        )

    __repr__=__str__




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


