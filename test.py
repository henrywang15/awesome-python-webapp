#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'

from models import User
from db import create_engine

create_engine(user='root', passwd='123', database='awesome')

u = User(name='Test', email='test@example.com', password='1234567890', image='about:blank')

u.insert()

# from web import view,get
# from web import WSGIApplication
# from web import Jinja2TemplateEngine
#
# @view('test.html')
# @get('/')
# def index():
#     return dict(name='wanglei')
#
#
# if __name__=='__main__':
#     server=WSGIApplication(r'/home/linaro/awesome-python-webapp/www')
#     server.template_engine=Jinja2TemplateEngine(r'/home/linaro/awesome-python-webapp/www/test')
#     server.add_url(index)
#     server.run(host='0.0.0.0')


