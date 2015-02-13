#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'

from time import time
from uuid import uuid4


def next_id(t=None):
    if t is None:
        t=time()
    return '{0:015}{1}000'.format(int(time()*1000),uuid4().hex)


