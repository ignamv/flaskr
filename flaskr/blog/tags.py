from ..db import get_db


def get_post_tags(post_id):
    return [row[0] for row in get_db().execute(
        'SELECT tag.name FROM tag JOIN post_tag'
        ' ON tag.id == post_tag.tag_id'
        ' WHERE post_tag.post_id == ?',
        (post_id,)
    ).fetchall()]
