from flask import (
    flash, g, redirect, render_template, request, session, url_for, abort
)
from ..db import get_db
from ..auth import login_required, get_user_id
from .comments import get_post_comments
from .blueprint import bp
from .blogdb import get_post
# Import to get the tag views registered with the blueprint as side-effect
from . import tags

@bp.route('/')
def index():
    user_id = get_user_id()
    posts = get_db().execute(
        'SELECT post.id, title, body, created, author_id, username, like.user_id NOTNULL AS liked'
        ' FROM post JOIN user ON post.author_id == user.id '
        ' LEFT JOIN like ON post.id == like.post_id AND like.user_id == ?'
        ' ORDER BY created DESC', (user_id,)).fetchall()
    return render_template('blog/posts.html', posts=posts)


@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        error = None
        title = request.form['title']
        if not title:
            error = 'Missing title'
        body = request.form['body']
        if not body:
            error = 'Missing body'
        if error is None:
            db = get_db()
            post_id = db.execute(
                'INSERT INTO post (author_id, title, body) VALUES (?,?,?)',
                (g.user['id'], title, body)
            ).lastrowid
            db.commit()
            return redirect(url_for('blog.post', post_id=post_id))
        else:
            flash(error)
    return render_template('blog/new.html')


@bp.route('/<int:post_id>')
def post(post_id):
    post = get_post(post_id, check_author=False)
    comments = get_post_comments(post_id)
    if post is None:
        flash('Invalid post')
        return redirect(url_for('index'))
    return render_template('blog/post.html', post=post, comments=comments)


@bp.route('/<int:post_id>/update', methods=('GET', 'POST'))
@login_required
def update(post_id):
    post = get_post(post_id)
    if request.method == 'POST':
        error = None
        title = request.form['title']
        if not title:
            error = 'Missing title'
        body = request.form['body']
        if not body:
            error = 'Missing body'
        if error is None:
            db = get_db()
            db.execute(
                'UPDATE post SET title = ?, body = ? WHERE id == ?',
                (title, body, post_id)
            )
            db.commit()
            return redirect(url_for('blog.post', post_id=post_id))
        else:
            flash(error)
    return render_template('blog/new.html', post_id=post_id, title=post['title'], body=post['body'])


@bp.route('/<int:post_id>/delete', methods=('POST',))
@login_required
def delete(post_id):
    get_post(post_id)
    db = get_db()
    db.execute('DELETE FROM post WHERE id == ?', (post_id,))
    db.commit()
    return redirect(url_for('index'))


@bp.route('/<int:post_id>/like', methods=('POST',))
@login_required
def like(post_id):
    db = get_db()
    new_status = int(request.form['like'])
    assert new_status in (0, 1)
    new_status = new_status == 1
    if db.execute('SELECT id FROM post WHERE id = ?', (post_id,)).fetchone() is None:
        abort(404)
    if new_status:
        db.execute('INSERT INTO like (post_id, user_id) VALUES (?, ?)', (post_id, g.user['id']))
    else:
        db.execute('DELETE FROM like WHERE post_id == ? AND user_id == ?', (post_id, g.user['id']))
    db.commit()
    return redirect(request.headers.get('Referer', '/'))
