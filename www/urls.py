#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'


from web import get,view

from models import User

@view('test_users.html')
@get('/')
def test_users():
    users=User.find_all()
    return dict(users=users)