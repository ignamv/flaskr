import pytest
from datetime import datetime
from unittest.mock import MagicMock
from flaskr.db import get_db
from flaskr.blog.blogdb import create_post, get_posts, count_posts, page_size
from flaskr.blog.tags import get_post_tags


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
        client.post('/create', data={'title': 'created', 'body': 'abody', 'tags': ''})
        assert count_posts() == original_count + 1


def test_update_view_mocking(client, monkeypatch, auth):
    post = {'title': 'asdf', 'body': 'poiuj', 'tags': ['b4', 't5']}
    mock_get_post = MagicMock(return_value=post)
    monkeypatch.setattr('flaskr.blog.get_post', mock_get_post)
    auth.login()
    response = client.get('/1/update')
    assert response.status_code == 200
    data = response.data.decode()
    assert post['title'] in data
    assert post['body'] in data
    assert ','.join(post['tags']) in data


def test_update(client, auth, app):
    auth.login()
    assert client.get('/1/update').status_code == 200
    client.post('/1/update', data={'id': 1, 'title': 'edited', 'body': 'edited', 'tags': ''})
    with app.app_context():
        db = get_db()
        post = db.execute('SELECT * FROM post WHERE id = 1').fetchone()
        assert post['title'] == 'edited'


@pytest.mark.parametrize('path', ('/create', '/1/update'))
def test_create_update_validate_input(auth, client, path):
    auth.login()
    response = client.post(path, data={'title': '', 'body': 'a', 'tags': ''})
    assert b'Missing title' in response.data
    response = client.post(path, data={'title': 'a', 'body': '', 'tags': ''})
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
        (1, 'tit1', 'body1', []),
        (2, 'tit2', 'body2', ['tag2']),
        (3, 'tit3', 'body3', ['tag2', 'tag3']),
        (4, 'tit4', 'body4', ['tag4', 'tag3']),
    ]
    with app.app_context():
        for author_id, title, body, tags in posts:
            oldcount = count_posts()
            create_post(author_id, title, body, tags)
            newcount = count_posts()
            assert newcount == oldcount + 1
            postcount = newcount
            post_id = get_db().execute(
                'SELECT id FROM post'
                ' WHERE author_id == ? AND title == ? AND body == ?',
                (author_id, title, body)
            ).fetchone()['id']
            actual_tags = set(get_post_tags(post_id))
            assert actual_tags == set(tags)


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
