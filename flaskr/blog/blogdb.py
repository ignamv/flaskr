from flask import g, abort

from ..db import get_db
from .tags import get_post_tags


def get_post(id, check_author=True):
    db = get_db()
    post = db.execute(
        "SELECT p.id, title, body, created, author_id, username"
        " FROM post p JOIN user u ON p.author_id = u.id"
        " WHERE p.id = ?",
        (id,),
    ).fetchone()
    if post is None:
        abort(404, f"Post id {id} does not exist")
    if check_author and (
        "user" not in g or g.user is None or post["author_id"] != g.user["id"]
    ):
        abort(403)
    if "user" not in g or g.user is None:
        liked = False
    else:
        user_id = g.user["id"]
        liked = (
            db.execute(
                "SELECT post_id FROM like WHERE post_id = ? AND user_id = ?",
                (id, user_id),
            ).fetchone()
            is not None
        )
    post = dict(post)
    post["liked"] = liked
    post["tags"] = get_post_tags(id)
    return post
