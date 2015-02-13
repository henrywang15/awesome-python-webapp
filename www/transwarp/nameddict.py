#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'


class Nameddict(dict):
    def __init__(self,names=(),values=(),**kwargs):
        super(Nameddict,self).__init__(**kwargs)
        for k,v in zip(names,values):
            self[k]=v

    def __setattr__(self, key, value):
        set[key]=value

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError('NamedObject has no attribute {}'.format(item))




