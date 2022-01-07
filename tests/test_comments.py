import pytest
import re
from flask import render_template, g
from flaskr.db import get_db
from flaskr.blog.comments import get_post_comments
from datetime import datetime
from unittest.mock import MagicMock

from test_auth import login_url


def test_get_post_comments(app):
    def dicts(rows):
        return list(map(dict, rows))

    with app.app_context():
        assert dicts(get_post_comments(1)) == [
            {
                "id": 1,
                "body": "comment11",
                "author_id": 1,
                "username": "test",
                "created": datetime(1911, 1, 1),
            },
            {
                "id": 2,
                "body": "comment12",
                "author_id": 2,
                "username": "other",
                "created": datetime(1912, 1, 1),
            },
        ]
        assert dicts(get_post_comments(2)) == [
            {
                "id": 3,
                "body": "comment21",
                "author_id": 1,
                "username": "test",
                "created": datetime(1921, 1, 1),
            },
            {
                "id": 4,
                "body": "comment22",
                "author_id": 2,
                "username": "other",
                "created": datetime(1922, 1, 1),
            },
        ]


@pytest.mark.parametrize("post_id", (1, 2))
def test_pass_through_comments(client, monkeypatch, post_id):
    comments = [
        {
            "id": 5,
            "body": f"comment{post_id}1",
            "author_id": 1,
            "username": "test",
            "created": datetime(1921, 1, 1),
        },
        {
            "id": 6,
            "body": f"comment{post_id}2",
            "author_id": 2,
            "username": "other",
            "created": datetime(1922, 1, 1),
        },
    ]
    mock_get_post_comments = MagicMock(return_value=comments)
    mock_render = MagicMock(return_value="")
    monkeypatch.setattr("flaskr.blog.get_post_comments", mock_get_post_comments)
    monkeypatch.setattr("flaskr.blog.render_template", mock_render)
    response = client.get(f"/{post_id}").data
    mock_get_post_comments.assert_called_once_with(post_id)
    mock_render.assert_called_once()
    assert mock_render.call_args[1]["comments"] == comments


@pytest.mark.parametrize("post_id", (1, 2))
def test_comments_rendering(app, post_id):
    comments = [
        {
            "id": 5,
            "body": f"comment{post_id}1",
            "author_id": 4,
            "username": f"test{post_id}",
            "created": datetime(1921, 1, 1),
        },
        {
            "id": 6,
            "body": f"comment{post_id}2",
            "author_id": 5,
            "username": f"other{post_id}",
            "created": datetime(1922, 1, 1),
        },
    ]
    post = {"id": post_id, "created": datetime(1234, 5, 6), "user": "theuser"}
    with app.test_request_context("/"):
        g.user = {"id": 1, "username": "asdf"}
        result = render_template("blog/post.html", post=post, comments=comments)
    assert re.search(
        ".*".join(
            (
                comments[0]["username"],
                comments[0]["created"].isoformat(" ", "minutes"),
                comments[0]["body"],
                comments[1]["username"],
                comments[1]["created"].isoformat(" ", "minutes"),
                comments[1]["body"],
            )
        ),
        result,
        re.DOTALL,
    )


def test_add_comment_nonexisting_post(client, auth):
    auth.login()
    assert client.get("/2000/comments/new").status_code == 404
    assert client.post("/2000/comments/new", data={"body": "asdf"}).status_code == 404


@pytest.mark.parametrize("post_id", (1, 2))
def test_add_comment(client, auth, post_id):
    assert client.get(f"/{post_id}/comments/new").headers["Location"] == login_url
    auth.login()
    assert client.get(f"/{post_id}/comments/new").status_code == 200
    print(client.post(f"/{post_id}/comments/new", data={"body": ""}).data)
    assert (
        b"Missing comment body"
        in client.post(f"/{post_id}/comments/new", data={"body": ""}).data
    )
    body = b"newcomment"
    assert (
        client.post(f"/{post_id}/comments/new", data={"body": body}).headers["Location"]
        == f"http://localhost/{post_id}"
    )
    assert body in client.get(f"/{post_id}").data


def test_missing_comment(client, auth):
    assert client.get("/2000/comments/1").status_code == 404


def test_existing_comment(client, auth):
    assert re.search(
        b"test title.*1911-01-01 00:00.*comment11",
        client.get("/1/comments/1").data,
        flags=re.DOTALL,
    )
    assert re.search(
        b"test2.*1921-01-01 00:00.*comment21",
        client.get("/2/comments/3").data,
        flags=re.DOTALL,
    )
