#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'

import re, hashlib, time
from web import get, view, ctx, post, interceptor,seeother,notfound
from apis import api, Page, APIError, APIValueError, APIPermissionError, APIResourceNotFoundError
from models import User, Blog, Comment
from config import configs
import markdown2

_COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret


_RE_MD5 = re.compile(r'^[0-9a-f]{32}$')
_RE_EMAIL = re.compile(r'^[a-z0-9\.\-_]+\@[a-z0-9\-_]+(\.[a-z0-9\-_]+){1,4}$')


def _get_page_index():
    page_index = 1
    try:
        page_index = int(ctx.request.get('page', '1'))
    except ValueError:
        pass
    return page_index

def _get_blogs_by_page():
    total = Blog.count_all()
    page= Page(total,_get_page_index())
    blogs = Blog.find_by('order by created_at desc limit ?,?',page.offset,page.limit)
    return blogs,page



@api
@get('/api/users')
def api_get_users():
    users = User.find_by('order by created_at desc')
    for user in users:
        user.password = '******'
    return dict(users=users)


@api
@post('/api/users')
def register_user():
    i = ctx.request.input(name='', email='', password='')
    name = i.name.strip()
    email = i.email.strip().lower()
    password = i.password
    if not name:
        raise APIValueError('name')
    if not email or not _RE_EMAIL.search(email):
        raise APIValueError('email')
    if not password or not _RE_MD5.search(password):
        raise APIValueError('password')
    user = User.find_first('where email=?', email)
    if user:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    user = User(name=name, email=email, password=password, image='http://www.gravatar.com/avatar/{}?d=mm&s=120'.
                format(hashlib.md5(email.encode('ascii')).hexdigest()))
    user.insert()
    cookie = make_signed_cookie(user.id, user.password, None)
    ctx.response.set_cookie(_COOKIE_NAME,cookie)
    return user


@view('register.html')
@get('/register')
def register():
    return dict()


@view('signin.html')
@get('/signin')
def signin():
    return dict()


def make_signed_cookie(id, password, max_age):
    # build cookie string by: id-expires-md5
    expires = str(int(time.time() + (max_age or 86400)))
    L = [id, expires, hashlib.md5('{}-{}-{}-{}'.format(id, password, expires, _COOKIE_KEY).encode('utf8')).hexdigest()]
    return '-'.join(L)

def parse_signed_cookie(cookie_str):
    try:
        L=cookie_str.split('-')
        if len(L) != 3:
            return None
        id, expires, md5 = L
        if int(expires) < time.time():
            return None
        user = User.get(id)
        if user is None:
            return None
        if md5 != hashlib.md5('{}-{}-{}-{}'.format(id, user.password, expires, _COOKIE_KEY).encode('utf8')).hexdigest():
            return None
        return user
    except Exception as e:
        return None

@api
@post('/api/authenticate')
def authenticate():
    i = ctx.request.input(remember='',email='',password='')
    email = i.email.strip().lower()
    password = i.password
    remember = i.remember
    user = User.find_first('where email=?',email)
    if user is None:
        raise APIError('auth:failed','email','Invalid email.')
    elif user.password != password:
        raise APIError('auth:failed','password','Invalid password.')
    max_age = 604800 if remember == 'true' else None
    cookie = make_signed_cookie(user.id, user.password, max_age)
    ctx.response.set_cookie(_COOKIE_NAME,cookie)
    return user

def check_admin():
    user = ctx.request.user
    if user and user.admin:
        return
    raise APIPermissionError('No permission.')


@interceptor('/manage/')
def manager_interceptor(next):
    user=ctx.request.user
    if user and user.admin:
        return next()
    raise seeother('/signin')


@interceptor('/')
def user_interceptor(next):
    user = None
    cookie = ctx.request.cookies.get(_COOKIE_NAME)
    if cookie:
        user=parse_signed_cookie(cookie)
    ctx.request.user = user
    return next()


@view('manage_blog_list.html')
@get('/manage/blogs')
def manage_blogs():
    page_index =_get_page_index()
    return dict(page_index=page_index,user=ctx.request.user)


@view('manage_blog_edit.html')
@get('/manage/blogs/create')
def manage_blogs_create():
    return dict(id=None, action='/api/blogs', redirect='/manage/blogs', user=ctx.request.user)


@view('manage_blog_edit.html')
@get('/manage/blogs/edit/:blog_id')
def manage_blogs_edit(blog_id):
    blog= Blog.get(blog_id)
    if blog is None:
        raise notfound()
    return dict(id=blog.id,name=blog.name,summary=blog.summary,content=blog.content,
                action='/api/blogs/{}'.format(blog_id),redirect='/manage/blogs',
                user=ctx.request.user)


@view('manage_comment_list.html')
@get('/manage/comments')
def manage_comments():
    page_index =_get_page_index()
    return dict(page_index=page_index,user=ctx.request.user)

@view('manage_user_list.html')
@get('/manage/users')
def manage_users():
    page_index =_get_page_index()
    return dict(page_index=page_index,user=ctx.request.user)



@api
@get('/api/comments')
def api_get_comments():
    total = Comment.count_all()
    page= Page(total,_get_page_index())
    comments = Comment.find_by('order by created_at desc limit ?,?',page.offset,page.limit)
    return dict(comments=comments,page=page)

@api
@post('/api/blogs/:blog_id/comments')
def api_create_blog_comment(blog_id):
    user = ctx.request.user
    if user is None:
        raise APIPermissionError('Need signin.')
    blog = Blog.get(blog_id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    content = ctx.request.input(content='').content.strip()
    if not content:
        raise APIValueError('content')
    c = Comment(blog_id=blog_id, user_id=user.id, user_name=user.name, user_image=user.image, content=content)
    c.insert()
    return dict(comment=c)


@api
@post('/api/comments/:comment_id/delete')
def api_delete_comment(comment_id):
    check_admin()
    comment = Comment.get(comment_id)
    if comment is None:
        raise APIResourceNotFoundError('Comment')
    comment.delete()
    return dict(id=comment_id)

@api
@get('/api/users')
def api_get_users():
    total = User.count_all()
    page= Page(total,_get_page_index())
    users = User.find_by('order by created_at desc limit ?,?',page.offset,page.limit)
    for u in users:
        u.password= '******'
    return dict(users=users,page=page)

@api
@get('/api/blogs')
def api_get_blogs():
    format= ctx.request.get('format','')
    blogs,page = _get_blogs_by_page()
    if format=='html':
        for blog in blogs:
            blog.content = markdown2.mardown(blog.content)
    return dict(blogs=blogs,page=page)

@api
@get('/api/blogs/:blog_id')
def api_get_blog(blog_id):
    blog = Blog.get(blog_id)
    if blog:
        return blog
    raise APIResourceNotFoundError('Blog')


@api
@post('/api/blogs')
def api_create_blog():
    check_admin()
    input = ctx.request.input(name='',summary='',content='')
    name=input.name.strip()
    summary=input.summary.strip()
    content=input.content.strip()
    if not name:
        raise APIValueError('name','name cannot be empty')
    if not summary:
        raise APIValueError('summary','summary cannot be empty')
    if not content:
        raise APIValueError('content','content cannot be empty')
    user=ctx.request.user
    blog = Blog(user_id=user.id,user_name=user.name,name=name,summary=summary,content=content)
    blog.insert()
    return blog

@api
@post('/api/blogs/:blog_id')
def api_update_blog(blog_id):
    check_admin()
    input= ctx.request.input(name='',summary='',content='')
    name=input.name.strip()
    summary=input.summary.strip()
    content=input.content.strip()
    if not name:
        raise APIValueError('name','name cannot be empty.')
    if not summary:
        raise APIValueError('summary','summary cannot be empty.')
    if not content:
        raise APIValueError('content','content cannot be empty.')
    blog = Blog.get(blog_id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    blog.name=name
    blog.summary=summary
    blog.content = content
    blog.update()

@api
@post('/api/blogs/:blog_id/delete')
def api_delete_blog(blog_id):
    check_admin()
    blog = Blog.get(blog_id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    blog.delete()
    return dict(id=blog_id)



@view('blogs.html')
@get('/')
def index():
    blogs, page = _get_blogs_by_page()
    return dict(page=page, blogs=blogs, user=ctx.request.user)


@view('blog.html')
@get('/blog/:blog_id')
def blog(blog_id):
    blog = Blog.get(blog_id)
    if blog is None:
        raise notfound()
    blog.html_content = markdown2.markdown(blog.content)
    comments = Comment.find_by('where blog_id=? order by created_at desc limit 1000', blog_id)
    return dict(blog=blog, comments=comments, user=ctx.request.user)


@get('/signout')
def signout():
    ctx.response.delete_cookie(_COOKIE_NAME)
    raise seeother('/')