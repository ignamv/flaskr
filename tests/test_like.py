import re
import pytest
from flaskr.blog.blogdb import get_post


def test_like_missing_post(client, auth):
    auth.login()
    assert client.post('/2000/like', data={'like': '1'}).status_code == 404


def test_like_redirects(client, auth):
    auth.login()
    response = client.post('/1/like', data={'like': '1'})
    assert response.headers['Location'] == 'http://localhost/'
    referer = 'http://localhost/the_referer'
    response = client.post('/2/like', data={'like': '1'}, headers={'Referer': referer})
    assert response.headers['Location'] == referer


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


@pytest.mark.parametrize(('post_id', 'expected_likes'), [(1, 0), (5, 1), (6, 2)])
def test_get_post_returns_likes(app, post_id, expected_likes):
    with app.app_context():
        post = get_post(post_id, check_author=False)
    assert post['likes'] == expected_likes


@pytest.mark.parametrize(('post_id', 'expected_likes'), [(1, 0), (5, 1), (6, 2)])
def test_like_count(client, post_id, expected_likes):
    print(client.get(f'/{post_id}').data.decode())
    assert f'Liked by {expected_likes} people' in client.get(f'/{post_id}').data.decode()
