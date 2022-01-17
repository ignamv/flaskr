from flask import flash, g, redirect, render_template, request, session, url_for, abort
from ..db import get_db
from ..auth import login_required, get_user_id
from .comments import get_post_comments
from .blueprint import bp
from .blogdb import (
    get_post,
    create_post,
    update_post,
    get_posts,
    count_posts,
    page_size,
)

# Import to register the views as a side-effect
from . import tags
from . import rss


@bp.route("/")
def index():
    user_id = get_user_id()
    page = int(request.args.get("page", 1))
    npages = max(1, (count_posts() - 1) // page_size + 1)
    if page < 1 or page > npages:
        return redirect(url_for(".index"))
    posts = get_posts(user_id, page)
    return render_template(
        "blog/posts.html", posts=posts, title="Latest posts", page=page, npages=npages
    )


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
        tags = request.form["tags"].split(",")
        imagebytes = request.files["file"].read() or None
        if error is None:
            post_id = create_post(g.user["id"], title, body, tags, imagebytes)
            return redirect(url_for("blog.post", post_id=post_id))
        else:
            flash(error)
    return render_template("blog/new.html")


@bp.route("/<int:post_id>")
def post(post_id):
    post = get_post(post_id, check_author=False)
    comments = get_post_comments(post_id)
    if post is None:
        flash("Invalid post")
        return redirect(url_for("index"))
    return render_template("blog/post.html", post=post, comments=comments)


@bp.route("/<int:post_id>/update", methods=("GET", "POST"))
@login_required
def update(post_id):
    post = get_post(post_id)
    if request.method == "POST":
        error = None
        title = request.form["title"]
        if not title:
            error = "Missing title"
        body = request.form["body"]
        if not body:
            error = "Missing body"
        tags = request.form["tags"].split(",")
        if tags == [""]:
            tags = []
        imagebytes = request.files["file"].read() or None
        delete_image = {"on": True, "off": False}[
            request.form.get("delete_image", "off")
        ]
        if delete_image and imagebytes is not None:
            abort(400)
        if error is None:
            update_post(post_id, title, body, tags, imagebytes, delete_image)
            return redirect(url_for("blog.post", post_id=post_id))
        else:
            flash(error)
    return render_template(
        "blog/new.html",
        post_id=post_id,
        title=post["title"],
        body=post["body"],
        tags=",".join(post["tags"]),
    )


@bp.route("/<int:post_id>/delete", methods=("POST",))
@login_required
def delete(post_id):
    get_post(post_id)
    db = get_db()
    db.execute("DELETE FROM post WHERE id == ?", (post_id,))
    db.commit()
    return redirect(url_for("index"))


@bp.route("/<int:post_id>/like", methods=("POST",))
@login_required
def like(post_id):
    db = get_db()
    new_status = int(request.form["like"])
    assert new_status in (0, 1)
    new_status = new_status == 1
    if db.execute("SELECT id FROM post WHERE id = ?", (post_id,)).fetchone() is None:
        abort(404)
    if new_status:
        db.execute(
            "INSERT INTO like (post_id, user_id) VALUES (?, ?)", (post_id, g.user["id"])
        )
    else:
        db.execute(
            "DELETE FROM like WHERE post_id == ? AND user_id == ?",
            (post_id, g.user["id"]),
        )
    db.commit()
    return redirect(request.headers.get("Referer", "/"))


@bp.route("/<int:post_id>/image.jpg")
def post_image(post_id):
    row = (
        get_db()
        .execute("SELECT imagebytes FROM post WHERE id == ?", (post_id,))
        .fetchone()
    )
    if row is None or row[0] is None:
        abort(404)
    return row[0]
