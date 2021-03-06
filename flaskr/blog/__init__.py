from datetime import datetime, timezone, timedelta
from flask import (
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    abort,
    current_app,
)
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
    get_post_image,
    get_posts_with_tag,
    get_tag_counts,
    get_last_post_time_for_user,
)
from ..recaptcha import validate_recaptcha_response, generate_recaptcha_html

# Import to register the views as a side-effect
from . import rss


class BadPageError(KeyError):
    pass


def show_posts(posts, post_count, title):
    page = int(request.args.get("page", 1))
    npages = max(1, (post_count - 1) // page_size + 1)
    if page < 1 or page > npages:
        raise BadPageError(page)
    result_number_string = build_result_number_string(page, page_size, post_count)
    return render_template(
        "blog/posts.html",
        posts=posts,
        title=title,
        page=page,
        npages=npages,
        result_number_string=result_number_string,
    )


@bp.route("/")
def index():
    searchquery = request.args.get("searchquery")
    page = int(request.args.get("page", 1))
    count, posts = get_posts(page=page, searchquery=searchquery)
    if not searchquery:
        title = "Latest posts"
    else:
        title = f'Search for "{searchquery}"'
    try:
        return show_posts(posts, count, title)
    except BadPageError:
        return redirect(url_for(".index"))


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        recaptcha_response = request.form["g-recaptcha-response"]
        if not title:
            error = "Missing title"
        elif not body:
            error = "Missing body"
        elif not recaptcha_response or not validate_recaptcha_response(
            recaptcha_response
        ):
            error = "Invalid captcha"
        elif does_user_exceed_post_rate_limit(g.user["id"]):
            error = "You must wait a little before posting again with this user"
        else:
            error = None
        tags = request.form["tags"].split(",")
        if tags == [""]:
            tags = []
        imagebytes = (
            request.files["file"].read() or None
        )  # TODO: only read if captcha valid?
        if error is None:
            post_id = create_post(g.user["id"], title, body, tags, imagebytes)
            return redirect(url_for("blog.post", post_id=post_id))
        else:
            flash(error)
    recaptcha_html = generate_recaptcha_html()
    return render_template("blog/new.html", recaptcha=recaptcha_html)


@bp.route("/<int:post_id>")
def post(post_id):
    post = get_post(post_id, check_author=False)
    comments = get_post_comments(post_id)
    if post is None:
        flash("Invalid post")
        return redirect(url_for("index"))
    likes = build_how_many_people_like_string(post["likes"], post["liked"])
    return render_template(
        "blog/post.html", post=post, comments=comments, likes=likes, single_post=True
    )


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
    return render_template("blog/new.html", post=post)


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
    try:
        imagebytes = get_post_image(post_id)
    except KeyError:
        abort(404)
    return imagebytes


def build_how_many_people_like_string(likes, liked):
    """Build string reporting how many people liked a post, specifying if the user liked it"""
    if likes == 0:
        return "no one so far"
    if likes == 1 and liked:
        return "you"
    likes -= liked
    you_and = "you and " if liked else ""
    other = " other" if liked else ""
    people = " people" if likes > 1 else " person"
    return you_and + str(likes) + other + people


def build_result_number_string(page, page_size, total_posts):
    if total_posts == 0:
        return "No posts were found"
    first_post = 1 + (page - 1) * page_size
    last_post = min(first_post + page_size - 1, total_posts)
    if last_post != first_post:
        return f"Showing posts {first_post}-{last_post} out of {total_posts}"
    return f"Showing post {first_post} out of {total_posts}"


@bp.route("/tags/<string:tag>")
def posts_with_tag(tag):
    page = int(request.args.get("page", 1))
    count, posts = get_posts_with_tag(tag, page=page)
    if not posts:
        abort(404)
    title = f'Posts tagged with "{tag}"'
    # TODO: redirect when page is invalid
    return show_posts(posts, count, title)


@bp.route("/tags/")
def tags():
    tag_counts = get_tag_counts()
    return render_template("blog/tags.html", tag_counts=tag_counts)


def does_user_exceed_post_rate_limit(user_id):
    last_post_time = get_last_post_time_for_user(user_id)
    if last_post_time is None:
        return False
    now = datetime.now(timezone.utc)
    delay = timedelta(seconds=current_app.config["POSTING_RATE_LIMIT_SECONDS"])
    print(
        f"Now {now} last_post_time {last_post_time} delay {delay} exceeds {now - last_post_time <= delay}"
    )
    return now - last_post_time <= delay
