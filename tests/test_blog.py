import re
import pytest
from flaskr.db import get_db


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


def count_posts(app):
    with app.app_context():
        db = get_db()
        return db.execute('SELECT COUNT(id) FROM post').fetchone()[0]


def test_create(client, auth, app):
    auth.login()
    original_count = count_posts(app)
    assert client.get('/create').status_code == 200
    client.post('/create', data={'title': 'created', 'body': 'abody'})
    assert count_posts(app) == original_count + 1


def test_update(client, auth, app):
    auth.login()
    assert client.get('/1/update').status_code == 200
    client.post('/1/update', data={'id': 1, 'title': 'edited', 'body': 'edited'})
    with app.app_context():
        db = get_db()
        post = db.execute('SELECT * FROM post WHERE id = 1').fetchone()
        assert post['title'] == 'edited'


@pytest.mark.parametrize('path', ('/create', '/1/update'))
def test_create_update_validate_input(auth, client, path):
    auth.login()
    response = client.post(path, data={'title': '', 'body': 'a'})
    assert b'Missing title' in response.data
    response = client.post(path, data={'title': 'a', 'body': ''})
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


def test_like_missing_post(client, auth):
    auth.login()
    assert client.post('/2000/like', data={'like': '1'}).status_code == 404


def test_like(client, auth):
    def like(user, post, status):
        auth.login(user)
        client.post(f'/{post}/like', data={'like': '1' if status else '0'})
        auth.logout()
    def assert_likes(user, likes1, likes2):
        auth.login(user)
        likes1 = b'Unlike' if likes1 else b'Like'
        likes2 = b'Unlike' if likes2 else b'Like'
        assert likes1 in client.get('/1').data
        assert likes2 in client.get('/2').data
        assert re.search(likes2 + b'.*' + likes1, client.get('/').data, flags=re.DOTALL)
        auth.logout()
    user1 = 'test'
    user2 = 'other'
    like(user2, 1, True)
    assert_likes(user2, True, False)
    assert_likes(user1, False, False)
    like(user1, 1, True)
    assert_likes(user1, True, False)
    like(user1, 2, True)
    assert_likes(user1, True, True)
    like(user1, 1, False)
    assert_likes(user1, False, True)
    like(user1, 2, False)
    assert_likes(user1, False, False)
    assert_likes(user2, True, False)

