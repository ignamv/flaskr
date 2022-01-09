import pytest
from unittest.mock import MagicMock
from flaskr.blog.tags import get_post_tags


alltags = {"tag1", "tag2"}


def test_display_tags_mocking_get_post_tags(client, monkeypatch):
    post_id = 1
    tags = ["tagA", "tag2", "tagQ"]
    mock_get_post_tags = MagicMock(return_value=tags)
    monkeypatch.setattr("flaskr.blog.blogdb.get_post_tags", mock_get_post_tags)
    response = client.get(f"/{post_id}").data.decode()
    mock_get_post_tags.assert_called_once_with(post_id)
    for tag in tags:
        assert tag in response


@pytest.mark.parametrize(
    "post_id,expected", [(1, []), (2, ["tag1"]), (3, ["tag2"]), (4, ["tag1", "tag2"])]
)
def test_get_post_tags(post_id, expected, app):
    with app.app_context():
        assert get_post_tags(post_id) == expected


@pytest.mark.parametrize(
    ("post_id", "tags"),
    [
        (1, set()),
        (2, {"tag1"}),
        (3, {"tag2"}),
        (4, {"tag1", "tag2"}),
    ],
)
def test_display_tags_e2e(client, post_id, tags):
    page = client.get(f"/{post_id}").data.decode()
    for tag in tags:
        assert tag in page
    for tag in alltags - tags:
        assert tag not in page
