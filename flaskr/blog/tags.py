from flask import render_template, g, abort
from ..db import get_db
from ..auth import get_user_id
from .blueprint import bp


def get_post_tags(post_id):
    return [
        row[0]
        for row in get_db()
        .execute(
            "SELECT tag.name FROM tag JOIN post_tag"
            " ON tag.id == post_tag.tag_id"
            " WHERE post_tag.post_id == ?",
            (post_id,),
        )
        .fetchall()
    ]


def get_posts_with_tag(tag, user_id):
    posts = [
        dict(row)
        for row in get_db()
        .execute(
            "SELECT post.id, title, body, created, author_id, username, has_image"
            " FROM posts_view post"
            " JOIN post_tag ON post_tag.post_id == post.id"
            " JOIN tag ON post_tag.tag_id == tag.id"
            " WHERE tag.name == ?"
            " ORDER BY created DESC",
            (tag,),
        )
        .fetchall()
    ]
    for post in posts:
        post["has_image"] = bool(post["has_image"])
    return posts


@bp.route("/tags/<string:tag>")
def posts_with_tag(tag):
    posts = get_posts_with_tag(tag, get_user_id())
    if not posts:
        abort(404)
    title = f'Posts tagged with "{tag}"'
    return render_template(
        "blog/posts.html", posts=posts, title=title, page=1, npages=1
    )
