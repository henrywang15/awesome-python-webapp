#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'

from models import User
from db import create_engine

create_engine(user='root', passwd='123', database='awesome')

u = User(name='Test', email='test@example.com', password='1234567890', image='about:blank')

u.insert()
