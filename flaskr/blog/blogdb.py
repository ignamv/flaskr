import sqlite3
from flask import g, abort

from ..db import get_db
from .tags import get_post_tags


page_size = 5


def get_post(id, check_author=True):
    db = get_db()
    post = db.execute(
        "SELECT p.id, title, body, created, author_id, username,"
        " imagebytes NOTNULL AS has_image"
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
    post["likes"] = db.execute(
        "SELECT COUNT(user_id) FROM like where post_id == ?", (id,)
    ).fetchone()[0]
    post["tags"] = get_post_tags(id)
    return post


def get_possibly_new_tag_id(tag):
    db = get_db()
    try:
        return db.execute("INSERT INTO tag (name) VALUES (?)", (tag,)).lastrowid
    except sqlite3.IntegrityError:
        return db.execute("SELECT id FROM tag WHERE name == ?", (tag,)).fetchone()["id"]


def add_tags_to_post(post_id, tags):
    db = get_db()
    for tag in tags:
        tag_id = get_possibly_new_tag_id(tag)
        db.execute(
            "INSERT INTO post_tag (post_id, tag_id) VALUES (?,?)", (post_id, tag_id)
        )


def create_post(author_id, title, body, tags, imagebytes):
    db = get_db()
    post_id = db.execute(
        "INSERT INTO post (author_id, title, body, imagebytes)" " VALUES (?,?,?,?)",
        (author_id, title, body, imagebytes),
    ).lastrowid
    add_tags_to_post(post_id, tags)
    db.commit()
    return post_id


def update_post(post_id, title, body, tags, imagebytes, delete_image):
    tags = set(tags)
    db = get_db()
    if (imagebytes is None) == delete_image:
        # Update image, whether to set a new one or to delete
        db.execute(
            "UPDATE post SET title = ?, body = ?, imagebytes = ?" " WHERE id == ?",
            (title, body, imagebytes, post_id),
        )
    elif not delete_image:
        # Leave image as-is
        db.execute(
            "UPDATE post SET title = ?, body = ? WHERE id == ?", (title, body, post_id)
        )
    else:
        # Passing an image while requesting deletion is invalid
        abort(400)
    current_tags = set(get_post_tags(post_id))
    to_be_removed_tags = current_tags - tags
    for tag in to_be_removed_tags:
        remove_post_tag(post_id, tag)
    to_be_added_tags = tags - current_tags
    add_tags_to_post(post_id, to_be_added_tags)
    db.commit()


def remove_post_tag(post_id, tag):
    db = get_db()
    tag_id = db.execute("SELECT id FROM tag WHERE name == ?", (tag,)).fetchone()["id"]
    db.execute(
        "DELETE FROM post_tag WHERE post_id == ? AND tag_id == ?", (post_id, tag_id)
    )


def get_posts(user_id, page=1, searchquery=None):
    """
    Return given page of posts. Optionally search title and body.

    user_id is used to determine which posts the user liked
    """
    if searchquery is not None:
        searchquery = "%" + searchquery + "%"
        where = " WHERE post.title LIKE :searchquery" " OR post.body LIKE :searchquery"
    else:
        where = ""
    fields = {
        "user_id": user_id,
        "page_size": page_size,
        "offset": page_size * (page - 1),
        "searchquery": searchquery,
    }
    posts = [
        dict(row)
        for row in get_db()
        .execute(
            "SELECT post.id, title, body, created, author_id, username,"
            " like.user_id NOTNULL AS liked,"
            " imagebytes NOTNULL AS has_image,"
            " COUNT(*) OVER() as resultcount"
            " FROM post JOIN user ON post.author_id == user.id "
            " LEFT JOIN like ON post.id == like.post_id AND like.user_id == :user_id"
            + where
            + " ORDER BY created DESC LIMIT :page_size OFFSET :offset",
            fields,
        )
        .fetchall()
    ]
    if posts:
        count = posts[0]["resultcount"]
    else:
        count = 0
    for post in posts:
        del post["resultcount"]
        post["liked"] = bool(post["liked"])
        post["has_image"] = bool(post["has_image"])
    return count, posts


def count_posts():
    return get_db().execute("SELECT COUNT(id) FROM post").fetchone()[0]
