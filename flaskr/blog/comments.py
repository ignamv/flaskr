from flask import request, redirect, url_for, abort, flash, render_template, g
from ..db import get_db
from ..auth import login_required
from .blogdb import get_post


routes = []
def route_later(*args, **kwargs):
    def wrapper(func):
        routes.append((func, args, kwargs))
        return func
    return wrapper


def register_routes(blueprint):
    for func, args, kwargs in routes:
        blueprint.route(*args, **kwargs)(func)


def get_post_comments(post_id):
    comments = get_db().execute(
        'SELECT comment.id, body, author_id, username, created'
        ' FROM comment JOIN user ON comment.author_id == user.id'
        ' WHERE post_id == ? ORDER BY created ASC',
        (post_id,)
    ).fetchall()
    return comments


@route_later('/<int:post_id>/comments/new', methods=('POST', 'GET'))
@login_required
def new_comment(post_id):
    db = get_db()
    if db.execute('SELECT id FROM post WHERE id == ?',
            (post_id,)).fetchone() is None:
        abort(404)
    if request.method == 'POST':
        body = request.form['body']
        if not body:
            flash('Missing comment body')
        else:
            db.execute(
                'INSERT INTO comment (post_id, author_id, body)'
                ' VALUES (?, ?, ?)',
                (post_id, g.user['id'], body)
            )
            db.commit()
            return redirect(url_for('blog.post', post_id=post_id))
    post = get_post(post_id, check_author=False)
    return render_template('blog/comments/new.html', post=post)
