import pytest
import re
from flask import render_template, g
from flaskr.db import get_db
from flaskr.blog.comments import get_post_comments
from datetime import datetime, timezone
from unittest.mock import MagicMock

from test_auth import login_url


def test_get_post_comments(app):
    def dicts(rows):
        return list(map(dict, rows))
    with app.app_context():
        assert dicts(get_post_comments(1)) == [
            {'id': 1, 'body': 'comment11', 'author_id': 1, 'username': 'test',
             'created': datetime(1911, 1, 1, tzinfo=timezone.utc)},
            {'id': 2, 'body': 'comment12', 'author_id': 2, 'username': 'other',
             'created': datetime(1912, 1, 1, tzinfo=timezone.utc)},
        ]
        assert dicts(get_post_comments(2)) == [
            {'id': 3, 'body': 'comment21', 'author_id': 1, 'username': 'test',
             'created': datetime(1921, 1, 1, tzinfo=timezone.utc)},
            {'id': 4, 'body': 'comment22', 'author_id': 2, 'username': 'other',
             'created': datetime(1922, 1, 1, tzinfo=timezone.utc)},
        ]


@pytest.mark.parametrize('post_id', (1, 2))
def test_pass_through_comments(client, monkeypatch, post_id):
    comments = [
        {'id': 5, 'body': f'comment{post_id}1', 'author_id': 1,
         'username': 'test', 'created': datetime(1921, 1, 1)},
        {'id': 6, 'body': f'comment{post_id}2', 'author_id': 2,
         'username': 'other',  'created': datetime(1922, 1, 1)},
    ]
    mock_get_post_comments = MagicMock(return_value=comments)
    mock_render = MagicMock(return_value='')
    monkeypatch.setattr('flaskr.blog.get_post_comments',
                        mock_get_post_comments)
    monkeypatch.setattr('flaskr.blog.render_template', mock_render)
    response = client.get(f'/{post_id}').data
    mock_get_post_comments.assert_called_once_with(post_id)
    mock_render.assert_called_once()
    assert mock_render.call_args[1]['comments'] == comments


@pytest.mark.parametrize('post_id', (1, 2))
def test_comments_rendering(app, post_id):
    comments = [
        {'id': 5, 'body': f'comment{post_id}1', 'author_id': 4,
         'username': f'test{post_id}', 'created': datetime(1921, 1, 1)},
        {'id': 6, 'body': f'comment{post_id}2', 'author_id': 5,
         'username': f'other{post_id}',  'created': datetime(1922, 1, 1)},
    ]
    post = {'id': post_id, 'created': datetime(1234, 5, 6), 'user': 'theuser'}
    with app.test_request_context('/'):
        g.user = {'id': 1, 'username': 'asdf'}
        result = render_template('blog/post.html', post=post,
                                 comments=comments)
    assert re.search('.*'.join((
        comments[0]['username'],
        comments[0]['created'].isoformat(' ', 'minutes'),
        comments[0]["body"],
        comments[1]['username'],
        comments[1]['created'].isoformat(' ', 'minutes'),
        comments[1]["body"],
    )), result, re.DOTALL)


def test_add_comment_nonexisting_post(client, auth):
    auth.login()
    assert client.get('/2000/comments/new').status_code == 404
    assert client.post('/2000/comments/new', data={'body': 'asdf'}
                       ).status_code == 404


@pytest.mark.parametrize('post_id', (1, 2))
def test_add_comment(client, auth, post_id):
    assert client.get(f'/{post_id}/comments/new'
                      ).headers['Location'] == login_url
    auth.login()
    assert client.get(f'/{post_id}/comments/new').status_code == 200
    print(client.post(f'/{post_id}/comments/new', data={'body': ''}).data)
    assert 'Missing comment body' in client.post(f'/{post_id}/comments/new',
                                                  data={'body': ''}).data.decode()
    body = 'newcomment'
    assert client.post(f'/{post_id}/comments/new', data={'body': body}
                       ).headers['Location'] == f'http://localhost/{post_id}'
    assert body in client.get(f'/{post_id}').data.decode()


def test_missing_comment(client, auth):
    assert client.get('/2000/comments/1').status_code == 404


def test_existing_comment(client, auth):
    assert re.search('test title.*1911-01-01 00:00.*comment11',
                     client.get('/1/comments/1').data.decode(), flags=re.DOTALL)
    assert re.search('test2.*1921-01-01 00:00.*comment21',
                     client.get('/2/comments/3').data.decode(), flags=re.DOTALL)


@pytest.mark.parametrize(
    'url',
    ('/{post_id}/comments/{comment_id}/delete',
     '/{post_id}/comments/{comment_id}/update'))
def test_edit_and_delete_comment_buttons(client, auth, url):
    # Make sure to test on a post made by another user
    # to check that the user id is compared against the *comment* author and
    # not the *post* author
    post_id = 2
    comment_id = 3
    change_url = url.format(post_id=post_id, comment_id=comment_id
                            ).encode('utf8')
    comment_url = f'/{post_id}/comments/{comment_id}'
    assert change_url not in client.get(comment_url).data
    auth.login('test')
    assert change_url in client.get(comment_url).data
    auth.logout()
    auth.login('other')
    assert change_url not in client.get(comment_url).data


def test_delete_missing_comment(client, auth):
    auth.login()
    assert client.post('/2000/comments/3000/delete').status_code == 404


def test_delete_auth(client, auth):
    assert client.post('/1/comments/1/delete').headers['Location'] == login_url
    auth.login('other')
    assert client.post('/1/comments/1/delete').status_code == 403
    auth.logout()
    auth.login()
    assert client.post('/1/comments/2/delete').status_code == 403
    assert client.post('/1/comments/1/delete').status_code == 302


def test_delete_deletes_and_what(client, auth):
    auth.login()
    assert client.post('/1/comments/1/delete').status_code == 302
    assert client.post('/1/comments/1/delete').status_code == 404
    # Make sure nothing else was deleted
    assert client.get('/1/comments/2').status_code == 200


def test_delete_redirects(client, auth):
    auth.login()
    assert client.post('/1/comments/1/delete').headers['Location'] == \
        'http://localhost/1'


def test_update_missing_comment(client, auth):
    auth.login()
    assert client.post('/2000/comments/3000/update').status_code == 404
    assert client.get('/2000/comments/3000/update').status_code == 404


def test_update_auth(client, auth):
    assert client.post('/1/comments/1/update').headers['Location'] == login_url
    auth.login('other')
    assert client.post('/1/comments/1/update').status_code == 403
    auth.logout()
    auth.login()
    assert client.post('/1/comments/2/update').status_code == 403
    assert client.get('/2/comments/3/update').status_code == 200
    assert client.post('/1/comments/1/update', data={'body': 'UPDATED'}
                       ).headers['Location'] == 'http://localhost/1'


def test_update_updates_and_what(client, auth):
    auth.login()
    assert client.post('/1/comments/1/update', data={'body': 'UPDATED'}
                       ).status_code == 302
    assert 'UPDATED' in client.get('/1/comments/1').data.decode()
    # Make sure nothing else was updated
    assert 'UPDATED' not in client.get('/1/comments/2').data.decode()


def test_update_post_redirects(client, auth):
    auth.login()
    assert client.post(
        '/1/comments/1/update',
        data={'body': 'UPDATED'}
    ).headers['Location'] == 'http://localhost/1'


def test_update_get_renders(client, auth):
    auth.login()
    assert client.get('/1/comments/1/update').status_code == 200
