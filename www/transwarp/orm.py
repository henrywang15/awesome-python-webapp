#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'

import logging
import db


def label(default, ddl):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if 'default' not in kwargs:
                kwargs['default'] = default
            if 'ddl' not in kwargs:
                kwargs['ddl'] = ddl
            func(*args, **kwargs)

        return wrapper

    return decorator


class Field:
    _count = 0
    fieldattr = {'name': None, 'default': None, 'primary_key': False, 'nullable': False,
                 'updatable': True, 'insertable': True, 'ddl': ''}

    def __init__(self, **kwargs):
        for attr, value in self.fieldattr.items():
            if kwargs.get(attr, None) is None:
                setattr(self, attr, value)
            else:
                setattr(self, attr, kwargs[attr])
        self._order = Field._count
        Field._count += 1

    @property
    def default(self):
        d = self._default
        return d() if callable(d) else d

    @default.setter
    def default(self, value):
        self._default = value


    def __str__(self):
        s = ['<{}:{},{},default({})'.format(self.__class__.__name__,
                                            self.name, self.ddl, self._default)]
        self.nullable and s.append('N')
        self.updatable and s.append('U')
        self.insertable and s.append('I')
        s.append('>')
        return ''.join(s)


class StringField(Field):
    @label('', 'varchar(255)')
    def __init__(self, **kwargs):
        super(StringField, self).__init__(**kwargs)


class IntegerField(Field):
    @label(0, 'bigint')
    def __init__(self, **kwargs):
        super(IntegerField, self).__init__(**kwargs)


class FloatField(Field):
    @label(0.0, 'real')
    def __init__(self, **kwargs):
        super(FloatField, self).__init__(**kwargs)


class BooleanField(Field):
    @label(False, 'bool')
    def __init__(self, **kwargs):
        super(BooleanField, self).__init__(**kwargs)


class TextField(Field):
    @label('', 'text')
    def __init__(self, **kwargs):
        super(TextField, self).__init__(**kwargs)


class BlobField(Field):
    @label('', 'blob')
    def __init__(self, **kwargs):
        super(BlobField, self).__init__(**kwargs)


class VersionField(Field):
    def __init__(self, name=None):
        super(VersionField, self).__init__(name=name, default=0, ddl='bigint')


_triggers = frozenset(['pre_insert', 'pre_update', 'pre_delete'])


def _gen_sql(table_name, mappings):
    pk = None
    sql = ['-- generating SQL for %s:' % table_name, 'create table `%s` (' % table_name]
    for f in sorted(mappings.values(), key=lambda x: x._order):
        if not hasattr(f, 'ddl'):
            raise AttributeError('no ddl in field "%s".' % n)
        ddl = f.ddl
        nullable = f.nullable
        if f.primary_key:
            pk = f.name
        sql.append(nullable and '  `%s` %s,' % (f.name, ddl) or '  `%s` %s not null,' % (f.name, ddl))
    sql.append('  primary key(`%s`)' % pk)
    sql.append(');')
    return '\n'.join(sql)


class ModelMetaclass(type):
    def __new__(meta, clsname, bases, ns):
        if clsname == 'Model':
            return type.__new__(meta, clsname, bases, ns)

        if not hasattr(meta, 'subclasses'):
            meta.subclasses = {}

        if clsname not in meta.subclasses:
            meta.subclasses[clsname] = clsname
        else:
            logging.warning('Redefine class: {}'.format(clsname))

        logging.info('Scan O-R Mapping {}...'.format(clsname))
        mappings = dict()
        primary_key = None
        for k, v in ns.items():
            if isinstance(v, Field):
                if not v.name:
                    v.name = k
                logging.info('Found Mapping {} => {}'.format(k, v))
                if v.primary_key:
                    if primary_key:
                        raise TypeError('Can\'t define more than \
                                1 primary key in class {}'.format(clsname))
                    if v.updatable:
                        logging.warning('Note:change primary key to non-updatable')
                        v.updatable = False
                    if v.nullable:
                        logging.warning('Note:change primary key to non-nullable')
                        v.nullable = False
                    primary_key = v
                mappings[k] = v
        if not primary_key:
            raise TypeError('Primary key not defined in class: {}'.format(clsname))
        for k in mappings.keys():
            del ns[k]
        if '__table__' not in ns:
            ns['__table__'] = clsname.lower()
        ns['__mappings__'] = mappings
        ns['__primary_key__'] = primary_key
        ns['__sql__'] = lambda self: _gen_sql(ns['__table__'], mappings)
        for trigger in _triggers:
            if trigger not in ns:
                ns[trigger] = None
        return type.__new__(meta, clsname, bases, ns)


class Model(dict, metaclass=ModelMetaclass):
    def __init__(self, **kwargs):
        super(Model, self).__init__(**kwargs)

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError('{} doesn\'t have such key'.format(self.__class__.__name__))

    def __setattr__(self, key, value):
        self[key] = value

    @classmethod
    def get(cls, pk):
        d = db.select_one('select * from {} where {}=?'.format(cls.__table__, cls.__primary_key__.name), pk)
        return cls(**d) if d else None

    @classmethod
    def find_first(cls, where, *args):
        d = db.select_one('select * from {} {}'.format(cls.__table__, where), *args)
        return cls(**d) if d else None

    @classmethod
    def find_all(cls, *args):
        L = db.select('select * from {}'.format(cls.__table__))
        return [cls(**d) for d in L]

    @classmethod
    def find_by(cls, where, *args):
        L = db.select('select * from {} {}'.format(cls.__table__, where), *args)
        return [cls(**d) for d in L]

    @classmethod
    def count_all(cls):
        return db.select_int('select count({}) from {}'.format(cls.__primary_key__.name, cls.__table__))

    @classmethod
    def count_by(cls, where, *args):
        return db.select_int('select count({}) from {} {}'.format(cls.__primary_key__.name, cls.__table__, where),
                             *args)

    def insert(self):
        self.pre_insert and self.pre_insert()
        params = {}
        for k, v in self.__mappings__.items():
            if v.insertable:
                if not hasattr(self, k):
                    setattr(self, k, v.default)
                params[v.name] = getattr(self, k)
        print(params)
        db.insert(self.__table__, **params)
        return self

    def update(self):
        self.pre_update and self.pre_update()
        L = []
        args = []
        for k, v in self.__mappings__.items():
            if v.updatable:
                if hasattr(self, k):
                    arg = getattr(self, k)
                else:
                    arg = v.default
                    setattr(self, k, arg)
                L.append('`{}`=?'.format(k))
                args.append(arg)
        pk = self.__primary_key__.name
        args.append(getattr(self, pk))
        # print('update `%s` set %s where %s=?' % (self.__table__, ','.join(L), pk), *args)
        db.update('update `%s` set %s where %s=?' % (self.__table__, ','.join(L), pk), *args)
        return self

    def delete(self):
        self.pre_delete and self.pre_delete()
        pk = self.__primary_key__.name
        args = (getattr(self, pk),)
        # print('delete from `%s` where `%s`=?' % (self.__table__, pk), *args)
        db.update('delete from `%s` where `%s`=?' % (self.__table__, pk), *args)
        return self




