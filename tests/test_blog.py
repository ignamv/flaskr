import re
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from io import BytesIO

from flaskr.db import get_db
from flaskr.blog.blogdb import (
    create_post, get_posts, count_posts, page_size,
    update_post, get_post, get_post_image)
from flaskr.blog import build_result_number_string
from flaskr.blog.tags import get_post_tags, get_posts_with_tag
from common import generate_no_file_selected, generate_file_tuple


def test_index(client, auth):
    response = client.get('/').data.decode()
    assert 'Log In' in response
    assert 'Register' in response

    auth.login()
    response = client.get('/').data.decode()
    strings = (
        'Log Out',
        'test title',
        'by test',
        '2018-01-01',
        'test\nbody',
        'href="/1/update"',
    )
    for string in strings:
        assert string in response


@pytest.mark.parametrize('path',
                         ('/create', '/1/update', '/1/delete', '/1/like'))
def test_login_required(client, auth, path):
    response = client.post(path)
    print(response.headers)
    print(response.data)
    assert response.headers['Location'] == 'http://localhost/auth/login'


def test_author_required(app, client, auth):
    with app.app_context():
        db = get_db()
        db.execute('UPDATE post SET author_id = 2 WHERE id = 1')
        db.commit()
    auth.login()
    # Can't edit or delete other user's post
    assert client.post('/1/update').status_code == 403
    assert client.post('/1/delete').status_code == 403
    # Can't see edit link for other user's post
    assert 'href="/1/update"' not in client.get('/').data.decode()


def test_exists_required(client, auth):
    auth.login()
    assert client.get('/2000/update').status_code == 404
    assert client.post('/2000/delete').status_code == 404


def test_create(client, auth, app):
    auth.login()
    with app.app_context():
        original_count = count_posts()
        assert client.get('/create').status_code == 200
        client.post('/create', data={'title': 'created', 'body': 'abody',
                                     'tags': '', 'file': (BytesIO(b''), '')})
        assert count_posts() == original_count + 1


@pytest.mark.parametrize('has_image', [False, True])
def test_update_view_mocking(client, monkeypatch, auth, has_image):
    post = {
        'id': 4,
        'title': 'asdf',
        'body': 'poiuj',
        'tags': ['b4', 't5'],
        'has_image': has_image
    }
    mock_get_post = MagicMock(return_value=post)
    monkeypatch.setattr('flaskr.blog.get_post', mock_get_post)
    auth.login()
    response = client.get('/1/update')
    assert response.status_code == 200
    data = response.data.decode()
    assert post['title'] in data
    assert post['body'] in data
    assert ('Delete existing image?' in data) == has_image
    assert ','.join(post['tags']) in data


@pytest.mark.parametrize('withfile', [False, True])
def test_update(client, auth, app, withfile):
    auth.login()
    assert client.get('/1/update').status_code == 200
    new_file_contents = b'edited_image'
    client.post('/1/update', content_type='multipart/form-data', data={
        'id': 1,
        'title': 'edited',
        'body': 'edited',
        'tags': '',
        'file': (BytesIO(new_file_contents if withfile else b''),
                 'image.jpg' if withfile else ''),
    })
    with app.app_context():
        db = get_db()
        post = db.execute('SELECT * FROM post WHERE id = 1').fetchone()
        assert post['title'] == 'edited'
        assert post['body'] == 'edited'
        if withfile:
            assert post['imagebytes'] == new_file_contents
        else:
            assert post['imagebytes'] == b'\xaa\xbb\xcc\xdd\xee\xff'


def test_update_function_changes_image(app, client):
    post_id = 1
    new_file_contents = b'edited_image'
    with app.app_context():
        update_post(post_id, 'newtit', 'newbod', 'newtag', new_file_contents,
                    False)
        assert client.get('/1/image.jpg').data == new_file_contents
        update_post(post_id, 'newtit', 'newbod', 'newtag', None, False)
        assert client.get('/1/image.jpg').data == new_file_contents
        update_post(post_id, 'newtit', 'newbod', 'newtag', None, True)
        assert client.get('/1/image.jpg').status_code == 404


@pytest.mark.parametrize('path', ('/create', '/1/update'))
def test_create_update_validate_input(auth, client, path):
    auth.login()
    response = client.post(path, data={'title': '', 'body': 'a', 'tags': '',
                                       'file': (BytesIO(b''), '')})
    assert 'Missing title' in response.data.decode()
    response = client.post(path, data={'title': 'a', 'body': '', 'tags': '',
                                       'file': (BytesIO(b''), '')})
    assert 'Missing body' in response.data.decode()


def test_delete(client, auth):
    auth.login()
    response = client.post('/1/delete')
    assert response.headers['Location'] == 'http://localhost/'
    assert 'test title' not in client.get('/').data.decode()


def test_singlepost(client):
    response = client.get('/2').data.decode()
    assert 'test title' not in response
    assert 'test2' in response


def test_create_post_function(app):
    posts = [
        (1, 'tit1', 'body1', [], b'some_image_bytes'),
        (2, 'tit2', 'body2', ['tag2'], None),
        (3, 'tit3', 'body3', ['tag2', 'tag3'], None),
        (4, 'tit4', 'body4', ['tag4', 'tag3'], None),
    ]
    with app.app_context():
        for author_id, title, body, tags, imagebytes in posts:
            oldcount = count_posts()
            create_post(author_id, title, body, tags, imagebytes)
            newcount = count_posts()
            assert newcount == oldcount + 1
            postcount = newcount
            post_id, actual_imagebytes = get_db().execute(
                'SELECT id, imagebytes FROM post'
                ' WHERE author_id == ? AND title == ? AND body == ?',
                (author_id, title, body)
            ).fetchone()
            actual_tags = set(get_post_tags(post_id))
            assert actual_tags == set(tags)
            assert actual_imagebytes == imagebytes


def test_index_title(client):
    assert '<title>Latest posts' in client.get('/').data.decode()


def generate_post(index):
    return {
        'id': index,
        'title': f'tit{index}',
        'body': f'body{index}',
        'created': datetime(2000 - index, 1, 1)
    }


@pytest.mark.parametrize('page', [1, 2, 3])
def test_posts_paging_mocking_get_posts(client, page, monkeypatch):
    npages = 3
    posts = [generate_post(ii) for ii in range(page_size)]
    mock_get_posts = MagicMock(return_value=(page_size*npages, posts))
    monkeypatch.setattr('flaskr.blog.get_posts', mock_get_posts)
    monkeypatch.setattr('flaskr.blog.count_posts', lambda: npages * page_size)
    mock_render = MagicMock(return_value='')
    monkeypatch.setattr('flaskr.blog.render_template', mock_render)
    response = client.get(f'/?page={page}').data.decode()
    mock_get_posts.assert_called_once_with(-1, page, searchquery=None)
    mock_render.assert_called_once_with('blog/posts.html', posts=posts,
                                        title='Latest posts', page=page,
                                        npages=npages)


def test_get_posts_function_paging(app):
    with app.app_context():
        total_posts = count_posts()
        lastpage = total_posts // page_size + 1
        for page in range(1, lastpage):
            assert len(get_posts(-1, page=page)[1]) == page_size
        assert len(get_posts(-1, page=lastpage)[1]) == \
            (total_posts - 1) % page_size + 1


@pytest.mark.parametrize('last_page_size', (1, page_size))
@pytest.mark.parametrize('page', range(7))
def test_page_links(client, monkeypatch, page, last_page_size):
    pages = 5
    mock_count_posts = MagicMock(return_value=(pages-1) * page_size +
                                 last_page_size)
    monkeypatch.setattr('flaskr.blog.count_posts', mock_count_posts)
    response = client.get(f'/?page={page}')
    mock_count_posts.assert_called_once_with()
    if page < 1 or page > pages:
        assert response.headers['Location'] == 'http://localhost/'
        return
    data = response.data.decode()
    assert (f'href="/?page={page-1}"' in data) == (page > 1)
    assert (f'href="/?page={page+1}"' in data) == (page < pages)


def test_count_posts(app):
    with app.app_context():
        assert count_posts() == 7
        get_db().execute('DELETE FROM post')
        assert count_posts() == 0


def find_image(responsedata, file_contents):
    urls = re.findall(r'"([^"]+.jpg)"', responsedata)
    for url in urls:
        if client.get(url).data == file_contents:
            return True
    return False


def test_get_post_image(client):
    response = client.get('/1/image.jpg').data
    assert response == b'\xaa\xbb\xcc\xdd\xee\xff'
    assert client.get('/2/image.jpg').status_code == 404
    assert client.get('/2000/image.jpg').status_code == 404


def test_posts_include_image(client):
    assert '<img src="/1/image.jpg"' in client.get('/1').data.decode()
    assert '<img src="/2/image.jpg"' not in client.get('/2').data.decode()


def test_create_uploading_image(client, auth):
    file_contents = b'somebytes'
    auth.login()
    response = client.post(
        '/create', content_type='multipart/form-data', data={
            'title': 'title of post with image',
            'body': 'body of post with image',
            'tags': 'file',
            'file': (BytesIO(file_contents), 'image.jpg'),
        })
    assert response.status_code == 302
    actual_image = client.get(response.headers['Location'] + '/image.jpg').data
    assert actual_image == file_contents


def test_no_posts(client, app):
    with app.app_context():
        get_db().execute('DELETE FROM post')
        assert client.get('/').status_code == 200


def test_create_uploading_no_image(client, auth):
    auth.login()
    response = client.post(
        '/create', content_type='multipart/form-data', data={
            'title': 'title of post without image',
            'body': 'body of post without image',
            'tags': 'nofile',
            'file': (BytesIO(b''), ''),
        })
    assert response.status_code == 302
    _, _, post_id = response.headers['Location'].rpartition('/')
    response = client.get(post_id).data.decode()
    assert f'<img src="/{post_id}/image.jpg"' not in response


# TODO: test create with no tags


@pytest.mark.parametrize(('file_', 'delete_image', 'expected_imagebytes',
                          'expected_deleteimage'), [
    (generate_no_file_selected(), 'off', None, False),
    (generate_no_file_selected(), 'on', None, True),
    (generate_file_tuple(b'123'), 'off', b'123', False),
])
def test_update_post_image(client, monkeypatch, auth, file_, delete_image,
                           expected_imagebytes, expected_deleteimage):
    """
    When no file was selected but image removal was not requested, pass no
    image data and do not request removal
    When no file was selected and image removal was requested, pass no image
    data and request removal
    When a file was selected and image removal was not requested, pass the
    image data and do not request removal
    """
    auth.login()
    mock = MagicMock()
    monkeypatch.setattr('flaskr.blog.update_post', mock)
    client.post('/1/update', data={
        'title': 'newtit',
        'body': 'bod',
        'tags': '',
        'file': file_,
        'delete_image': delete_image,
    }, content_type='multipart/form-data')
    mock.assert_called_once_with(1, 'newtit', 'bod', [], expected_imagebytes,
                                 expected_deleteimage)


def test_update_post_image_fails_when_image_passed_and_deletion_requested(
        client, monkeypatch, auth):
    """
    """
    auth.login()
    mock = MagicMock()
    monkeypatch.setattr('flaskr.blog.update_post', mock)
    assert client.post('/1/update', data={
        'title': 'newtit',
        'body': 'bod',
        'tags': '',
        'file': generate_file_tuple(b'123'),
        'delete_image': 'on',
    }, content_type='multipart/form-data').status_code == 400


@pytest.mark.parametrize('has_image', [False, True])
@pytest.mark.parametrize('liked', [False, True])
def test_view_post_mocking_get_post(client, monkeypatch, has_image, liked):
    post = {
        'id': 123,
        'title': 'tit',
        'body': 'bod',
        'has_image': has_image,
        'likes': 3,
        'liked': liked,
        'tags': [],
        'created': datetime(1900, 1, 1),
    }
    mock_get_post = MagicMock(return_value=post)
    monkeypatch.setattr('flaskr.blog.get_post', mock_get_post)
    response = client.get('/123').data.decode()
    mock_get_post.assert_called_once_with(123, check_author=False)
    assert post['title'] in response
    assert post['body'] in response
    assert ('<img src="/123/image.jpg"' in response) == has_image
    if liked:
        assert f'Liked by you and {post["likes"]-1} other people' in response
    else:
        assert f'Liked by {post["likes"]} people' in response


def test_index_search(app):
    # Search in body, case insensitive
    post, = get_posts(-1, 1, searchquery='bOdY2')[1]
    assert post['title'] == 'test2'
    # Search in title
    post, = get_posts(-1, 1, searchquery='test title')[1]
    assert post['title'] == 'test title'


@pytest.mark.parametrize(('page', 'page_size', 'total_posts', 'expected'), [
    (1, 5, 0, 'No posts were found'),
    (1, 5, 1, 'Showing post 1 out of 1'),
    (1, 5, 2, 'Showing posts 1-2 out of 2'),
    (1, 5, 7, 'Showing posts 1-5 out of 7'),
    (2, 5, 7, 'Showing posts 6-7 out of 7'),
])
def test_result_number_function(page, page_size, total_posts, expected):
    assert build_result_number_string(page, page_size, total_posts) == expected


@pytest.mark.xfail()
@pytest.mark.parametrize(
    ('url', 'expected_first', 'expected_last', 'expected_total'), [
        ('/', 1, 5, 7),
        ('/?page=2', 6, 7, 7),
        ('/tags/tag1', 1, 2, 2),
    ]
)
def test_index_shows_number_of_results(url, expected_first, expected_last,
                                       expected_total):
    response = client.get(url).data.decode()
    first, last, total = map(int, re.search(
        r'Showing results\s*(\d+)-(\d+)\s*from (\d+)', 
        response, flags=re.DOTALL
    ).groups())
    assert first == expected_first
    assert last == expected_last
    assert total == expected_total


def test_create_post_created_date_argument(app):
    db = get_db()
    # Default: created date is current date
    postid = create_post(author_id=1, title='title', body='body', tags=[], imagebytes=None)
    post = get_post(postid, False)
    print(post['created'])
    assert abs(
        (post['created'] - datetime.now(timezone.utc)).total_seconds()
    ) < 5
    # Optional: specify creation time
    some_datetime = datetime(2019, 3, 4, tzinfo=timezone.utc)
    postid = create_post(author_id=1, title='title', body='body', tags=[], imagebytes=None, created=some_datetime)
    post = get_post(postid, False)
    print(post['created'])
    assert post['created'] == some_datetime


def generate_posts(nposts):
    db = get_db()
    db.execute('DELETE FROM post')
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
    return posts
@pytest.mark.parametrize('nposts', range(page_size*2 + 1))
def test_get_posts_and_get_post_image(nposts, app):
    """Test get_post, get_posts and get_post_image with many sets of posts"""
    # What fields are returned by get_posts() and get_posts_with_tag()
    fields_getposts = (
        'author_id',
        'title',
        'body',
        'created',
        'id',
        'has_image',
        'username',
    )
    # What fields are returned by get_post()
    fields_getpost = fields_getposts + (
        'tags',
        'liked',
        'likes',
    )
    posts = generate_posts(nposts)
    pages = [posts[start:start+page_size] for start in range(0, max(len(posts), 1), page_size)]
    for pagenumber, page in enumerate(pages, 1):
        count, actual_posts = get_posts(-1, pagenumber)
        assert count == nposts
        assert len(actual_posts) == len(page)
        for actual, expected in zip(actual_posts, page):
            expected_getpost = {k: v for k, v in expected.items()
                                 if k in fields_getpost}
            assert get_post(expected['id'], False) == expected_getpost
            expected_getposts = {k: v for k, v in expected.items()
                                 if k in fields_getposts}
            assert actual == expected_getposts
            if expected['has_image']:
                assert get_post_image(expected['id']) == expected['imagebytes']
            else:
                with pytest.raises(KeyError):
                    get_post_image(expected['id'])
    all_tags = {tag for post in posts for tag in post['tags']}
    for tag in all_tags:
        expected_posts_with_tag = [post for post in posts if tag in post['tags']]
        actual_posts_with_tag = get_posts_with_tag(tag, -1)
        assert len(expected_posts_with_tag) == len(actual_posts_with_tag)
        for expected, actual in zip(expected_posts_with_tag, actual_posts_with_tag):
            expected = {k: v for k, v in expected.items()
                                 if k in fields_getposts}
            assert actual == expected
