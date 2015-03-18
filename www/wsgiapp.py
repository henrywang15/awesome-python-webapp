#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'

import os

import logging; logging.basicConfig(level=logging.INFO)

import db
from web import WSGIApplication,Jinja2TemplateEngine
from config import configs

db.create_engine(**configs.db)

wsgi=WSGIApplication(os.path.dirname(os.path.abspath(__file__)))
wsgi.template_engine=Jinja2TemplateEngine(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))

import urls
wsgi.add_module(urls)

if __name__=='__main__':
    wsgi.run()