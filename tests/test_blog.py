import re
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from io import BytesIO

from flaskr.db import get_db
from flaskr.blog.blogdb import create_post, get_posts, count_posts, page_size, update_post
from flaskr.blog.tags import get_post_tags
from common import generate_no_file_selected, generate_file_tuple


def test_index(client, auth):
    response = client.get('/')
    assert b'Log In' in response.data
    assert b'Register' in response.data

    auth.login()
    response = client.get('/')
    strings = (
        b'Log Out',
        b'test title',
        b'by test',
        b'on 2018-01-01',
        b'test\nbody',
        b'href="/1/update"',
    )
    for string in strings:
        assert string in response.data


@pytest.mark.parametrize('path', ('/create', '/1/update', '/1/delete', '/1/like'))
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
    assert b'href="/1/update"' not in client.get('/').data


def test_exists_required(client, auth):
    auth.login()
    assert client.get('/2000/update').status_code == 404
    assert client.post('/2000/delete').status_code == 404


def test_create(client, auth, app):
    auth.login()
    with app.app_context():
        original_count = count_posts()
        assert client.get('/create').status_code == 200
        client.post('/create', data={'title': 'created', 'body': 'abody', 'tags': '', 'file': (BytesIO(b''), '')})
        assert count_posts() == original_count + 1


@pytest.mark.parametrize('has_image', [False, True])
def test_update_view_mocking(client, monkeypatch, auth, has_image):
    post = {
        'id': 4,
        'title': 'asdf',
        'body': 'poiuj',
        'tags': ['b4',
        't5'],
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
        update_post(post_id, 'newtit', 'newbod', 'newtag', new_file_contents, False)
        assert client.get('/1/image.jpg').data == new_file_contents
        update_post(post_id, 'newtit', 'newbod', 'newtag', None, False)
        assert client.get('/1/image.jpg').data == new_file_contents
        update_post(post_id, 'newtit', 'newbod', 'newtag', None, True)
        assert client.get('/1/image.jpg').status_code == 404


@pytest.mark.parametrize('path', ('/create', '/1/update'))
def test_create_update_validate_input(auth, client, path):
    auth.login()
    response = client.post(path, data={'title': '', 'body': 'a', 'tags': '', 'file': (BytesIO(b''), '')})
    assert b'Missing title' in response.data
    response = client.post(path, data={'title': 'a', 'body': '', 'tags': '', 'file': (BytesIO(b''), '')})
    assert b'Missing body' in response.data


def test_delete(client, auth):
    auth.login()
    response = client.post('/1/delete')
    assert response.headers['Location'] == 'http://localhost/'
    assert b'test title' not in client.get('/').data


def test_singlepost(client):
    response = client.get('/2').data
    assert b'test title' not in response
    assert b'test2' in response


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
    assert b'<title>Latest posts' in client.get('/').data


def generate_post(index):
    return {
        'id': index,
        'title': f'tit{index}',
        'body': f'body{index}',
        'created': datetime(2000 - index, 1, 1)
    }


@pytest.mark.parametrize('page', [1,2,3])
def test_posts_paging_mocking_get_posts(client, page, monkeypatch):
    npages = 3
    posts = [generate_post(ii) for ii in range(page_size)]
    mock_get_posts = MagicMock(return_value=posts)
    monkeypatch.setattr('flaskr.blog.get_posts', mock_get_posts)
    monkeypatch.setattr('flaskr.blog.count_posts', lambda: npages * page_size)
    mock_render = MagicMock(return_value='')
    monkeypatch.setattr('flaskr.blog.render_template', mock_render)
    response = client.get(f'/?page={page}').data.decode()
    mock_get_posts.assert_called_once_with(-1, page, )
    mock_render.assert_called_once_with('blog/posts.html', posts=posts, title='Latest posts', page=page, npages=npages)


def test_get_posts_function(app):
    with app.app_context():
        total_posts = count_posts()
        lastpage = total_posts // page_size + 1
        for page in range(1, lastpage):
            assert len(get_posts(-1, page=page)) == page_size
        assert len(get_posts(-1, page=lastpage)) == (total_posts - 1) % page_size + 1


@pytest.mark.parametrize('last_page_size', (1, page_size))
@pytest.mark.parametrize('page', range(7))
def test_page_links(client, monkeypatch, page, last_page_size):
    pages = 5
    mock_count_posts = MagicMock(return_value=(pages-1) * page_size + last_page_size)
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
    assert b'<img src="/1/image.jpg"' in client.get('/1').data
    assert b'<img src="/2/image.jpg"' not in client.get('/2').data


def test_create_uploading_image(client, auth):
    file_contents = b'somebytes'
    auth.login()
    response = client.post('/create', content_type='multipart/form-data', data={
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
    response = client.post('/create', content_type='multipart/form-data', data={
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


@pytest.mark.parametrize(('file_', 'delete_image', 'expected_imagebytes', 'expected_deleteimage'), [
    (generate_no_file_selected(), 'off', None, False),
    (generate_no_file_selected(), 'on', None, True),
    (generate_file_tuple(b'123'), 'off', b'123', False),
])
def test_update_post_image(client, monkeypatch, auth, file_, delete_image,
        expected_imagebytes, expected_deleteimage):
    """
    When no file was selected but image removal was not requested, pass no image data and do not request removal
    When no file was selected and image removal was requested, pass no image data and request removal
    When a file was selected and image removal was not requested, pass the image data and do not request removal
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
    mock.assert_called_once_with(1, 'newtit', 'bod', [], expected_imagebytes, expected_deleteimage)


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
def test_view_post_mocking_get_post(client, monkeypatch, has_image):
    post = {
        'id': 123,
        'title': 'tit',
        'body': 'bod',
        'has_image': has_image,
        'likes': 3,
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
    assert f'Liked by {post["likes"]} people' in response
