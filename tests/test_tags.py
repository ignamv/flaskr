from collections import defaultdict
from flask import url_for
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from flaskr.blog.blogdb import (
    remove_post_tag, update_post, get_post_tags, get_posts_with_tag,
    get_tag_counts, get_possibly_new_tag_id)
from flaskr.db import get_db
from flaskr.recaptcha import recaptcha_always_passes_context
from sqlite3 import IntegrityError
from common import generate_no_file_selected, generate_file_tuple, generate_posts


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


def test_display_posts_with_tag_mocking_find_posts_with_tag(client,
                                                            monkeypatch):
    posts = [
        {'id': 1, 'title': 'title1', 'body': 'body1',
         'created': datetime.now()},
        {'id': 2, 'title': 'title2', 'body': 'body2',
         'created': datetime.now()},
        {'id': 3, 'title': 'title3', 'body': 'body3',
         'created': datetime.now()},
    ]
    mock = MagicMock(return_value=(len(posts), posts))
    monkeypatch.setattr('flaskr.blog.get_posts_with_tag', mock)
    response = client.get('/tags/thetag').data.decode()
    mock.assert_called_once_with('thetag', page=1)
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
        count, posts = get_posts_with_tag(tag, page=1)
    assert count == len(expected_titles)
    actual_titles = {post['title'] for post in posts}
    assert actual_titles == expected_titles


def test_posts_with_tag_e2e(client):
    assert client.get('/tags/missing_tag').status_code == 404


@pytest.mark.parametrize('tags', [{'tag1', 'tag2'}, {'tag3'}])
def test_update_post_tags_integration(client, tags, app, auth):
    auth.login()
    data = {'title': 'newtit', 'body': 'bod', 'tags': ','.join(tags),
            'file': generate_no_file_selected()}
    assert client.post('/1/update', data=data
                       ).headers['Location'] == 'http://localhost/1'
    with app.app_context():
        assert set(get_post_tags(1)) == tags


def test_update_post_tags_mocking(client, monkeypatch, auth):
    auth.login()
    for tags in [['tag1', 'tag2'], ['tag3']]:
        mock = MagicMock()
        monkeypatch.setattr('flaskr.blog.update_post', mock)
        data = {'title': 'newtit', 'body': 'bod', 'tags': ','.join(tags),
                'file': generate_no_file_selected()}
        assert client.post('/1/update', data=data
                           ).headers['Location'] == 'http://localhost/1'
        mock.assert_called_once_with(1, data['title'], data['body'], tags,
                                     None, False)


def test_update_post_tags_function(app):
    post_id = 1
    with app.app_context():
        for tags in [['tag1', 'tag2'], ['tag2', 'tag3'], ['tag3']]:
            update_post(post_id, 'newtit', 'bod', tags, None, False)
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
    data = {'title': 'created', 'body': 'abody', 'tags': 'tag1,tag2',
            'file': generate_no_file_selected(),
            'g-recaptcha-response': '123'}
    with recaptcha_always_passes_context():
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
    data = {'title': 'created', 'body': 'abody', 'tags': ','.join(tags),
            'file': generate_no_file_selected(),
            'g-recaptcha-response': '123'}
    with recaptcha_always_passes_context():
        client.post('/create', data=data)
    author_id = 1
    mock.assert_called_once()
    assert mock.call_args[0][:4] == (author_id, data['title'], data['body'],
                                     tags)


def test_posts_with_tag_title(client):
    assert '<title>Posts tagged with &#34;tag1&#34;' in client.get(
        '/tags/tag1').data.decode()


def test_tags_page_mocking_get_tag_counts(monkeypatch, client, app):
    tag_counts = [('tagA', 23), ('tagB', 46)]
    mock_get_tag_counts = MagicMock(return_value=tag_counts)
    monkeypatch.setattr('flaskr.blog.get_tag_counts', mock_get_tag_counts)
    response = client.get(url_for('blog.tags', _external=True)
                          ).data.decode()
    mock_get_tag_counts.assert_called_once_with()
    for tag, count in tag_counts:
        assert f'>{tag} ({count})</a>' in response
        url = url_for('blog.posts_with_tag', tag=tag)
        assert f'href="{url}"' in response


@pytest.mark.parametrize('nposts', range(13))
def test_get_tag_counts(nposts, app):
    expected_count = defaultdict(lambda: 0)
    posts = generate_posts(nposts)
    for post in posts:
        for tag in post['tags']:
            expected_count[tag] += 1
    actual_count = get_tag_counts()
    counts_without_tagname = [count for tag, count in actual_count]
    # Should be sorted in decreasing order
    assert counts_without_tagname == sorted(counts_without_tagname, reverse=True)
    for tag, count in actual_count:
        assert count == expected_count[tag]


def test_empty_tags_forbidden(app):
    db = get_db()
    with pytest.raises(IntegrityError):
        db.execute('INSERT INTO tag (name) VALUES ("")')


def test_get_possibly_new_tag_id_rejects_empty_tag(app):
    with pytest.raises(AssertionError):
        get_possibly_new_tag_id('')
