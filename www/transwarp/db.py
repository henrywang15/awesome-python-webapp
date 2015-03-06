__author__ = 'linaro'

import threading
import logging
from functools import wraps
from time import time
from nameddict import Nameddict

def _profiling(start,sql=''):
    t=time()-start
    if t>0.1:
        logging.warning('[Profiling] [DB] {} {}'.format(t,sql))
    logging.info('[Profiling] [DB] {} {}'.format(t,sql))

class DBError(Exception):
    pass

class MultiColumnsError(DBError):
    pass

class _LazyConnection:
    def __init__(self):
        self.connection=None

    def cursor(self):
        if self.connection is None:
            connection=engine.connect()
            logging.info('open connection {}'.format(hex(id(connection))))
            self.connection=connection
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()

    def roolback(self):
        self.connection.rollback()

    def cleanup(self):
        if self.connection:
            connection=self.connection
            self.connection=None
            logging.info('close connection {}'.format(hex(id(connection))))
            connection.close()




class _Engine:
    def __init__(self,connect):
        self._connect=connect

    def connect(self):
        return self._connect()

engine=None


def create_engine(user,passwd,database,host='127.0.0.1',port=3306,**kwargs):
    import mysql.connector
    global engine
    if engine is not None:
        raise DBError('Engine has been initialized')
    params=dict(user=user,passwd=passwd,database=database,host=host,port=port)
    defaults=dict(use_unicode=True,charset='utf8',collation='utf8_general_ci',autocommit=False)
    params.update(defaults,**kwargs)
    params['buffered']=True
    engine=_Engine(lambda:mysql.connector.connect(**params))
    logging.info("Init mysql engine {} ok".format(hex(id(engine))))

create_engine(user='root', passwd='123', database='awesome')

class _DbContex(threading.local):
    def __init__(self):
        self.connection=None
        self.transactions=0

    def is_init(self):
        return not self.connection is None

    def init(self):
        self.connection=_LazyConnection()
        self.transactions=0

    def cleanup(self):
        self.connection.cleanup()
        self.connection=None

    def cursor(self):
        return self.connection.cursor()

# create a threading local object which will be share by multiple threads
# without caring about lock problem
_db_ctx=_DbContex()



class _ConnectionCtx:
    def __enter__(self):
        global _db_ctx
        self.should_cleanup=False
        if not _db_ctx.is_init():
            _db_ctx.init()
            self.should_cleanup=True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _db_ctx
        if self.should_cleanup:
            _db_ctx.cleanup()

def connection():
    return _ConnectionCtx()

def with_connection(func):
    @wraps(func)
    def wrapper(*args,**kwargs):
        with _ConnectionCtx():
            return func(*args,**kwargs)
    return wrapper


def _select(sql,first,*args):
    global _db_ctx
    cursor=None
    sql=sql.replace('?','%s')
    logging.info('SQL {},ARGS:{}'.format(sql,args))
    try:
        cursor=_db_ctx.connection.cursor()
        cursor.execute(sql,args)
        if cursor.description:
            names=[x[0] for x in cursor.description]
        if first:
            values=cursor.fetchone()
            if not values:
                return None
            return Nameddict(names,values)
        return [Nameddict(names,values) for values in cursor.fetchall()]
    finally:
        if cursor:
            cursor.close()


@with_connection
def select_one(sql,*args):
    return _select(sql,True,*args)

@with_connection
def select_int(sql,*args):
    d=_select(sql,True,*args)
    if len(d)!=1:
        raise MultiColumnsError('Expected only one column.')
    return d.values()[0]

@with_connection
def select(sql,*args):
    return _select(sql,False,*args)

@with_connection
def _update(sql,*args):
    global _db_ctx
    cursor=None
    sql=sql.replace('?','%s')
    logging.info('SQL: {} ARGS:{}'.format(sql,args))
    try:
        cursor=_db_ctx.connection.cursor()
        cursor.execute(sql,args)
        r=cursor.rowcount
        if _db_ctx.transactions==0:
            logging.info('auto commit')
            _db_ctx.connection.commit()
        return r
    finally:
        if cursor:
            cursor.close()


def insert(table_name,**kwargs):
    cols,args=zip(*kwargs.items())
    sql='insert into {} ({}) values ({})'.format(table_name
    ,','.join([col for col in cols]),','.join(['?' for i in range(len(cols))]))
    print(sql)
    return _update(sql,*args)

def update(sql,*args):
    return _update(sql,*args)


class _TransactionCtx:
    def __enter__(self):
        global _db_ctx
        self.should_close_conn=False
        if not _db_ctx.is_init():
            _db_ctx.init()
            self.should_close_conn=True
        _db_ctx.transactions+=1
        logging.info("begin transaction..." if _db_ctx.transactions==1 else 'join current transaction...')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _db_ctx
        _db_ctx.transactions-=1
        try:
            if _db_ctx.transactions==0:
                if exc_type is None:
                    self.commit()
                else:
                    self.rollback()
        finally:
            if self.should_close_conn:
                _db_ctx.cleanup()

    def commit(self):
        global _db_ctx
        logging.info('commit transaction...')
        try:
            _db_ctx.connection.commit()
            logging.info('commit ok')
        except:
            logging.warning('commit failed. try rollback...')
            _db_ctx.connection.rollback()
            logging.warning('rollback ok.')
            raise

    def rollback(self):
        global _db_ctx
        logging.warning('rollback transaction...')
        _db_ctx.connection.rollback()
        logging.info('rollback ok.')

def transaction():
    return _TransactionCtx()

def with_transaction(func):
    @wraps(func)
    def wrapper(*args,**kwargs):
        _start=time()
        with _TransactionCtx():
            return func(*args,**kwargs)
        _profiling(_start)
    return wrapper


