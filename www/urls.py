#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'


from web import get, view
from apis import api
from models import User, Blog


@view('blogs.html')
@get('/')
def index():
    blogs = Blog.find_all()
    user = User.find_first('where email=?', 'admin@example.com')
    return dict(blogs=blogs,user=user)


@api
@get('/api/users')
def api_get_users():
    users=User.find_by('order by created_at desc')
    for user in users:
        user.password = '******'
    return dict(users=users)