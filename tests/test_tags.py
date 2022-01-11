import pytest
from datetime import datetime
from unittest.mock import MagicMock
from flaskr.blog.tags import get_post_tags, get_posts_with_tag
from flaskr.blog.blogdb import remove_post_tag, update_post


alltags = {'tag1', 'tag2'}


def test_display_tags_mocking_get_post_tags(client, monkeypatch):
    post_id = 1
    tags = ['tagA', 'tag2', 'tagQ']
    mock_get_post_tags = MagicMock(return_value=tags)
    monkeypatch.setattr('flaskr.blog.blogdb.get_post_tags', mock_get_post_tags)
    response = client.get(f'/{post_id}').data.decode()
    mock_get_post_tags.assert_called_once_with(post_id)
    print(response)
    for tag in tags:
        assert f'href="/tags/{tag}"' in response


@pytest.mark.parametrize('post_id,expected', [
    (1, []), (2, ['tag1']), (3, ['tag2']), (4, ['tag1', 'tag2'])])
def test_get_post_tags(post_id, expected, app):
    with app.app_context():
        assert get_post_tags(post_id) == expected


@pytest.mark.parametrize(('post_id', 'tags'), [
    (1, set()),
    (2, {'tag1'}),
    (3, {'tag2'}),
    (4, {'tag1', 'tag2'}),
])
def test_display_tags_e2e(client, post_id, tags):
    page = client.get(f'/{post_id}').data.decode()
    for tag in tags:
        assert tag in page
    for tag in alltags - tags:
        assert tag not in page


def test_display_posts_with_tag_mocking_find_posts_with_tag(client, monkeypatch):
    posts = [
        {'id': 1, 'title': 'title1', 'body': 'body1', 'created': datetime.now()},
        {'id': 2, 'title': 'title2', 'body': 'body2', 'created': datetime.now()},
        {'id': 3, 'title': 'title3', 'body': 'body3', 'created': datetime.now()},
    ]
    mock = MagicMock(return_value=posts)
    monkeypatch.setattr('flaskr.blog.tags.get_posts_with_tag', mock)
    response = client.get('/tags/thetag').data.decode()
    mock.assert_called_once_with('thetag', -1)
    for post in posts:
        assert post['title'] in response
        assert post['body'] in response


@pytest.mark.parametrize('tag,expected_titles', [
    ('faketag', set()),
    ('tag1', {'test2', 'test4'}),
    ('tag2', {'test3', 'test4'}),
])
def test_get_posts_with_tag(app, tag, expected_titles):
    untagged = ['test title']
    with app.app_context():
        posts = get_posts_with_tag(tag, -1)
    actual_titles = {post['title'] for post in posts}
    assert actual_titles == expected_titles


def test_posts_with_tag_e2e(client):
    assert client.get('/tags/missing_tag').status_code == 404


@pytest.mark.parametrize('tags', [{'tag1', 'tag2'}, {'tag3'}])
def test_update_post_tags_integration(client, tags, app, auth):
    auth.login()
    data = {'title': 'newtit', 'body': 'bod', 'tags': ','.join(tags)}
    assert client.post('/1/update', data=data).headers['Location'] == 'http://localhost/1'
    with app.app_context():
        assert set(get_post_tags(1)) == tags


def test_update_post_tags_mocking(client, monkeypatch, auth):
    auth.login()
    for tags in [['tag1', 'tag2'], ['tag3']]:
        mock = MagicMock(return_value=123)
        monkeypatch.setattr('flaskr.blog.update_post', mock)
        data = {'title': 'newtit', 'body': 'bod', 'tags': ','.join(tags)}
        assert client.post('/1/update', data=data).headers['Location'] == 'http://localhost/1'
        mock.assert_called_once_with(1, data['title'], data['body'], tags)


def test_update_post_tags_function(app):
    post_id = 1
    with app.app_context():
        for tags in [['tag1', 'tag2'], ['tag2', 'tag3'], ['tag3']]:
            update_post(post_id, 'newtit', 'bod', tags)
            assert set(get_post_tags(post_id)) == set(tags)


def test_remove_tag(app):
    post_id = 2
    tag = 'tag1'
    with app.app_context():
        assert get_post_tags(post_id) == [tag]
        remove_post_tag(post_id, tag)
        assert get_post_tags(post_id) == []


def test_create_with_tag_integration(client, auth, app):
    auth.login()
    data = {'title': 'created', 'body': 'abody', 'tags': 'tag1,tag2'}
    post_url = client.post('/create', data=data).headers['Location']
    response = client.get(post_url).data.decode()
    assert data['title'] in response
    assert data['body'] in response
    for tag in data['tags'].split(','):
        assert f'href="/tags/{tag}"' in response


def test_create_with_tag_mocking_insert(client, auth, app, monkeypatch):
    mock = MagicMock(return_value=1234)
    monkeypatch.setattr('flaskr.blog.create_post', mock)
    auth.login()
    tags = ['tag1', 'tag2']
    data = {'title': 'created', 'body': 'abody', 'tags': ','.join(tags)}
    client.post('/create', data=data)
    author_id = 1
    mock.assert_called_once_with(author_id, data['title'], data['body'], tags)


def test_posts_with_tag_title(client):
    assert b'<title>Posts tagged with &#34;tag1&#34;' in client.get('/tags/tag1').data
