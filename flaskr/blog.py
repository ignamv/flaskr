from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    abort,
)
from .db import get_db
from .auth import login_required

bp = Blueprint("blog", __name__)


@bp.route("/")
def index():
    posts = (
        get_db()
        .execute(
            "SELECT p.id, title, body, created, author_id, username"
            " FROM post p JOIN user u ON p.author_id = u.id "
            "ORDER BY created DESC"
        )
        .fetchall()
    )
    return render_template("blog/posts.html", posts=posts)


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    if request.method == "POST":
        error = None
        title = request.form["title"]
        if not title:
            error = "Missing title"
        body = request.form["body"]
        if not body:
            error = "Missing body"
        if error is None:
            db = get_db()
            post_id = db.execute(
                "INSERT INTO post (author_id, title, body) VALUES (?,?,?)",
                (g.user["id"], title, body),
            ).lastrowid
            db.commit()
            print(post_id)
            return redirect(url_for("blog.post", post_id=post_id))
        else:
            flash(error)
    return render_template("blog/new.html")


@bp.route("/<int:post_id>/")
def post(post_id):
    post = get_db().execute("SELECT * FROM post WHERE id == ?", (post_id,)).fetchone()
    if post is None:
        flash("Invalid post")
        return redirect(url_for("index"))
    print(post)
    return render_template("blog/post.html", post=post)


def get_post(id, check_author=True):
    post = (
        get_db()
        .execute(
            "SELECT p.id, title, body, created, author_id, username"
            " FROM post p JOIN user u ON p.author_id = u.id"
            " WHERE p.id = ?",
            (id,),
        )
        .fetchone()
    )
    if post is None:
        abort(404, f"Post id {id} does not exist")
    if check_author and (
        "user" not in g or g.user is None or post["author_id"] != g.user["id"]
    ):
        abort(403)
    return post


@bp.route("/<int:post_id>/update", methods=("GET", "POST"))
@login_required
def update(post_id):
    post = get_post(post_id)
    print(dict(post))
    if request.method == "POST":
        error = None
        title = request.form["title"]
        if not title:
            error = "Missing title"
        body = request.form["body"]
        if not body:
            error = "Missing body"
        if error is None:
            db = get_db()
            db.execute(
                "UPDATE post SET title = ?, body = ? WHERE id == ?",
                (title, body, post_id),
            )
            db.commit()
            return redirect(url_for("blog.post", post_id=post_id))
        else:
            flash(error)
    return render_template(
        "blog/new.html", post_id=post_id, title=post["title"], body=post["body"]
    )


@bp.route("/<int:post_id>/delete", methods=("POST",))
@login_required
def delete(post_id):
    get_post(post_id)
    db = get_db()
    db.execute("DELETE FROM post WHERE id == ?", (post_id,))
    db.commit()
    return redirect(url_for("index"))
