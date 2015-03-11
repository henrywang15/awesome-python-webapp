#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'

import datetime
import re

RE_TZ = re.compile(r'^([\+\-])([0-9]{1,2})\:([0-9]{1,2})$')
TIMEDELTA_ZERO=datetime.timedelta(0)

class UTC(datetime.tzinfo):
    def __init__(self,utc):
        utc=utc.strip().upper()
        mt=RE_TZ.search(utc)
        if mt:
            minus=mt.group(1)=='-'
            h=int(mt.group(2))
            m=int(mt.group(3))
            if minus:
                h,m=-h,-m
            self._utcoffset=datetime.timedelta(hours=h,minutes=m)
            self._tzname='UTC{}'.format(utc)

    def utcoffset(self,dt):
        return self._utcoffset

    def dst(self,dt):
        return TIMEDELTA_ZERO

    def tzname(self,dt):
        return self._tzname

    def __str__(self):
        return 'UTC tzinfo object ({})'.format(self._tzname)

    __repr__=__str__






