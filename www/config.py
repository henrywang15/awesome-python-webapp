#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'

import config_default
from nameddict import Nameddict

configs = config_default.configs


def merge(defaults, user):
    r = {}
    for k, v in defaults.items():
        if k in user:
            if isinstance(v, dict):
                r[k] = merge(v, user[k])
            else:
                r[k] = user[k]
        else:
            r[k] = v
    return r


def toNamedDict(d):
    nd = Nameddict()
    for k, v in d.items():
        nd[k] = toNamedDict(v) if isinstance(v, dict) else v
    return nd


try:
    import config_user

    configs = toNamedDict(merge(configs, config_user.configs))
except ImportError:
    pass

