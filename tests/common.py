from io import BytesIO
from flaskr.blog.blogdb import create_post
from flaskr.db import get_db
from datetime import datetime, timezone


def generate_no_file_selected():
    return (BytesIO(b''), '')


def generate_file_tuple(contents):
    return BytesIO(contents), 'filename.jpg'


def generate_posts(nposts):
    db = get_db()
    db.execute('DELETE FROM post')
    db.execute('DELETE FROM tag')
    db.execute('DELETE FROM post_tag')
    db.commit()
    posts = []
    for ii in range(nposts):
        # Only even posts have image, odd posts don't
        has_image = ii % 2 == 0
        post = {
            # Alternate two posts from author 1, two from author 2
            'author_id': (ii & 2) // 2 + 1,
            'title': f'title{ii}',
            'body': '\n'.join([f'body{ii}'] + 
                              [f'line{line}' for line in range(ii+1)]),
            'imagebytes': None if not has_image else f'imagedata{ii}'.encode(),
            # Post N has tags tag1..tagN
            'tags': [f'tag{ntag}' for ntag in range(1, ii + 1)],
            'created': datetime(2000 + ii, 2, 3, 11, 58, 23, tzinfo=timezone.utc)
        }
        postid = create_post(**post)
        post.update({
            'id': postid,
            'has_image': has_image,
            'liked': False,
            'likes': 0,
            'username': {1: 'test', 2: 'other'}[post['author_id']],
        })
        posts.insert(0, post)
    return sorted(posts, key=lambda post: post['created'], reverse=True)
