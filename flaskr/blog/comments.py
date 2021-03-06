from flask import (
    request,
    redirect,
    url_for,
    abort,
    flash,
    render_template,
    g,
    current_app,
)
from datetime import datetime, timezone, timedelta
from ..db import get_db
from ..auth import login_required
from .blogdb import get_post, create_comment, get_last_comment_time_for_user
from .blueprint import bp
from ..recaptcha import generate_recaptcha_html, validate_recaptcha_response


def get_post_comments(post_id):
    comments = (
        get_db()
        .execute(
            "SELECT comment.id, body, author_id, username, created"
            " FROM comment JOIN user ON comment.author_id == user.id"
            " WHERE post_id == ? ORDER BY created ASC",
            (post_id,),
        )
        .fetchall()
    )
    return comments


@bp.route("/<int:post_id>/comments/new", methods=("POST", "GET"))
@login_required
def new_comment(post_id):
    db = get_db()
    if db.execute("SELECT id FROM post WHERE id == ?", (post_id,)).fetchone() is None:
        abort(404)
    if request.method == "POST":
        error = True
        body = request.form["body"]
        recaptcha_response = request.form["g-recaptcha-response"]
        if not body:
            flash("Missing comment body")
        elif not recaptcha_response or not validate_recaptcha_response(
            recaptcha_response
        ):
            flash("Invalid captcha")
        elif does_user_exceed_comment_rate_limit(g.user["id"]):
            flash("You must wait a little before commenting again with this user")
        else:
            error = False
        if not error:
            comment_id = create_comment(
                post_id, g.user["id"], body, created=datetime.now()
            )
            db.commit()
            return redirect(
                url_for("blog.post", post_id=post_id, _anchor=f"comment{comment_id}")
            )
    post = get_post(post_id, check_author=False)
    recaptcha_html = generate_recaptcha_html()
    return render_template(
        "blog/comments/new.html", post=post, recaptcha=recaptcha_html
    )


def get_comment(post_id, comment_id):
    ret = (
        get_db()
        .execute(
            "SELECT comment.id, user.username, comment.author_id, comment.created,"
            " comment.body"
            " FROM comment JOIN user ON comment.author_id == user.id"
            " WHERE post_id == ? AND comment.id == ?",
            (post_id, comment_id),
        )
        .fetchone()
    )
    if ret is None:
        abort(404)
    return ret


@bp.route("/<int:post_id>/comments/<int:comment_id>")
def comment(post_id, comment_id):
    post = get_post(post_id, check_author=False)
    comment = get_comment(post_id, comment_id)
    return render_template("blog/comments/comment.html", post=post, comment=comment)


@bp.route("/<int:post_id>/comments/<int:comment_id>/delete", methods=("POST",))
@login_required
def delete_comment(post_id, comment_id):
    comment = get_comment(post_id, comment_id)
    if comment["author_id"] != g.user["id"]:
        abort(403)
    db = get_db()
    db.execute("DELETE FROM comment WHERE id == ?", (comment_id,))
    db.commit()
    return redirect(url_for("blog.post", post_id=post_id))


@bp.route("/<int:post_id>/comments/<int:comment_id>/update", methods=("GET", "POST"))
@login_required
def update_comment(post_id, comment_id):
    post = get_post(post_id, check_author=False)
    comment = get_comment(post_id, comment_id)
    if request.method == "POST":
        if comment["author_id"] != g.user["id"]:
            abort(403)
        body = request.form["body"]
        db = get_db()
        db.execute("UPDATE comment SET body = ? WHERE id = ?", (body, comment_id))
        db.commit()
        return redirect(url_for("blog.post", post_id=post_id))
    return render_template("blog/comments/new.html", post=post, comment=comment)


def does_user_exceed_comment_rate_limit(user_id):
    last_comment_time = get_last_comment_time_for_user(user_id)
    if last_comment_time is None:
        return False
    now = datetime.now(timezone.utc)
    delay = timedelta(seconds=current_app.config["COMMENTING_RATE_LIMIT_SECONDS"])
    print(
        f"Now {now} last_comment_time {last_comment_time} delay {delay} exceeds {now - last_comment_time <= delay}"
    )
    return now - last_comment_time <= delay
