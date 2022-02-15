import sqlite3
from flask import g, abort

from ..db import get_db


page_size = 5


def get_post(id, check_author=True):
    db = get_db()
    post = db.execute(
        "SELECT p.id, title, body, created, author_id, username, has_image"
        " FROM posts_view p WHERE p.id = ?",
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


def create_post(author_id, title, body, tags, imagebytes, created=None):
    db = get_db()
    fields = {
        "author_id": author_id,
        "title": title,
        "body": body,
        "imagebytes": imagebytes,
        "created": created,
    }
    cols = ["author_id", "title", "body", "imagebytes"]
    if created is not None:
        cols.append("created")
    post_id = db.execute(
        "INSERT INTO post (" + ",".join(cols) + ")"
        " VALUES (" + ",".join(":" + col for col in cols) + ")",
        fields,
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


def get_posts(page=1, searchquery=None):
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
        "page_size": page_size,
        "offset": page_size * (page - 1),
        "searchquery": searchquery,
    }
    posts = [
        dict(row)
        for row in get_db()
        .execute(
            "SELECT post.id, title, body, created, author_id, username, has_image,"
            " COUNT(*) OVER() as resultcount"
            " FROM posts_view post"
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
        post["has_image"] = bool(post["has_image"])
    return count, posts


def count_posts():
    return get_db().execute("SELECT COUNT(id) FROM post").fetchone()[0]


def get_post_image(post_id):
    row = (
        get_db()
        .execute("SELECT imagebytes FROM post WHERE id == ?", (post_id,))
        .fetchone()
    )
    if row is None or row[0] is None:
        raise KeyError
    return row[0]


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


def get_posts_with_tag(tag, page):
    posts = [
        dict(row)
        for row in get_db()
        .execute(
            "SELECT post.id, title, body, created, author_id, username, has_image,"
            " COUNT(*) OVER() as resultcount"
            " FROM posts_view post"
            " JOIN post_tag ON post_tag.post_id == post.id"
            " JOIN tag ON post_tag.tag_id == tag.id"
            " WHERE tag.name == :tag"
            " ORDER BY created DESC LIMIT :page_size OFFSET :offset",
            {"tag": tag, "page_size": page_size, "offset": page_size * (page - 1)},
        )
        .fetchall()
    ]
    if posts:
        count = posts[0]["resultcount"]
    else:
        count = 0
    for post in posts:
        post["has_image"] = bool(post["has_image"])
        del post["resultcount"]
    return count, posts


def get_tag_counts():
    """Return list of (tag name, # of posts with this tag) pairs"""
    return (
        get_db()
        .execute(
            "SELECT tag.name, count(*) AS count"
            " FROM tag JOIN post_tag ON tag.id == post_tag.tag_id"
            " GROUP BY tag.name"
            " ORDER BY count DESC"
        )
        .fetchall()
    )
