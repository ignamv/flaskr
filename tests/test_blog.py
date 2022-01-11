import pytest
from unittest.mock import MagicMock
from flaskr.db import get_db
from flaskr.blog.blogdb import create_post
from flaskr.blog.tags import get_post_tags


def test_index(client, auth):
    response = client.get("/")
    assert b"Log In" in response.data
    assert b"Register" in response.data

    auth.login()
    response = client.get("/")
    strings = (
        b"Log Out",
        b"test title",
        b"by test",
        b"on 2018-01-01",
        b"test\nbody",
        b'href="/1/update"',
    )
    for string in strings:
        assert string in response.data


@pytest.mark.parametrize("path", ("/create", "/1/update", "/1/delete", "/1/like"))
def test_login_required(client, auth, path):
    response = client.post(path)
    print(response.headers)
    print(response.data)
    assert response.headers["Location"] == "http://localhost/auth/login"


def test_author_required(app, client, auth):
    with app.app_context():
        db = get_db()
        db.execute("UPDATE post SET author_id = 2 WHERE id = 1")
        db.commit()
    auth.login()
    # Can't edit or delete other user's post
    assert client.post("/1/update").status_code == 403
    assert client.post("/1/delete").status_code == 403
    # Can't see edit link for other user's post
    assert b'href="/1/update"' not in client.get("/").data


def test_exists_required(client, auth):
    auth.login()
    assert client.get("/2000/update").status_code == 404
    assert client.post("/2000/delete").status_code == 404


def count_posts(app):
    with app.app_context():
        db = get_db()
        return db.execute("SELECT COUNT(id) FROM post").fetchone()[0]


def test_create(client, auth, app):
    auth.login()
    original_count = count_posts(app)
    assert client.get("/create").status_code == 200
    client.post("/create", data={"title": "created", "body": "abody", "tags": ""})
    assert count_posts(app) == original_count + 1


def test_update_view_mocking(client, monkeypatch, auth):
    post = {"title": "asdf", "body": "poiuj", "tags": ["b4", "t5"]}
    mock_get_post = MagicMock(return_value=post)
    monkeypatch.setattr("flaskr.blog.get_post", mock_get_post)
    auth.login()
    response = client.get("/1/update")
    assert response.status_code == 200
    data = response.data.decode()
    assert post["title"] in data
    assert post["body"] in data
    assert ",".join(post["tags"]) in data


def test_update(client, auth, app):
    auth.login()
    assert client.get("/1/update").status_code == 200
    client.post(
        "/1/update", data={"id": 1, "title": "edited", "body": "edited", "tags": ""}
    )
    with app.app_context():
        db = get_db()
        post = db.execute("SELECT * FROM post WHERE id = 1").fetchone()
        assert post["title"] == "edited"


@pytest.mark.parametrize("path", ("/create", "/1/update"))
def test_create_update_validate_input(auth, client, path):
    auth.login()
    response = client.post(path, data={"title": "", "body": "a", "tags": ""})
    assert b"Missing title" in response.data
    response = client.post(path, data={"title": "a", "body": "", "tags": ""})
    assert b"Missing body" in response.data


def test_delete(client, auth):
    auth.login()
    response = client.post("/1/delete")
    assert response.headers["Location"] == "http://localhost/"
    assert b"test title" not in client.get("/").data


def test_singlepost(client):
    response = client.get("/2").data
    assert b"test title" not in response
    assert b"test2" in response


def test_create_post_function(app):
    posts = [
        (1, "tit1", "body1", []),
        (2, "tit2", "body2", ["tag2"]),
        (3, "tit3", "body3", ["tag2", "tag3"]),
        (4, "tit4", "body4", ["tag4", "tag3"]),
    ]
    with app.app_context():
        for author_id, title, body, tags in posts:
            oldcount = count_posts(app)
            create_post(author_id, title, body, tags)
            newcount = count_posts(app)
            assert newcount == oldcount + 1
            postcount = newcount
            post_id = (
                get_db()
                .execute(
                    "SELECT id FROM post"
                    " WHERE author_id == ? AND title == ? AND body == ?",
                    (author_id, title, body),
                )
                .fetchone()["id"]
            )
            actual_tags = set(get_post_tags(post_id))
            assert actual_tags == set(tags)
