import pytest
from io import BytesIO
from unittest.mock import MagicMock
from flask import url_for
from flaskr.blog.blogdb import create_post, create_comment
from flaskr.blog import does_user_exceed_post_rate_limit
from flaskr.auth_db import register_user
from flaskr.auth import does_ip_exceed_registration_rate_limit
from flaskr.blog.comments import does_user_exceed_comment_rate_limit
from datetime import datetime, timezone, timedelta


def generate_registration_postdata(index):
    return {
        "username": f"user{index}",
        "password": f"password{index}",
        "g-recaptcha-response": "123",
    }


def test_registration_rate_limit_checker_firstregistration(app):
    """IP with no users never exceeds rate limit"""
    assert not does_ip_exceed_registration_rate_limit("1.2.3.4")


@pytest.mark.usefixtures("recaptcha_always_passes")
def test_registration_checks_rate_limit(client, app, monkeypatch):
    ip = "10.0.0.1"
    url = url_for("auth.register")
    error = "You must wait a little before registering more users from this computer"
    mock_check_rate_limit = MagicMock(return_value=True)
    monkeypatch.setattr(
        "flaskr.auth.does_ip_exceed_registration_rate_limit", mock_check_rate_limit
    )
    response = client.post(
        url, data=generate_registration_postdata(1), environ_base={"REMOTE_ADDR": ip}
    )
    assert response.status_code == 200
    assert error in response.data.decode()
    assert mock_check_rate_limit.called_once_with(ip)

    mock_check_rate_limit.return_value = False
    response = client.post(
        url, data=generate_registration_postdata(1), environ_base={"REMOTE_ADDR": ip}
    )
    assert response.status_code == 302


@pytest.mark.usefixtures("recaptcha_always_passes")
def test_registration_rate_limit_checker(client, app, monkeypatch):
    delay = timedelta(seconds=37)
    second = timedelta(seconds=1)
    app.config["REGISTRATION_RATE_LIMIT_SECONDS"] = delay.total_seconds()
    now = datetime(2030, 2, 3, tzinfo=timezone.utc)
    mock_now = MagicMock(return_value=now)

    class MockDatetime:
        now = mock_now

    monkeypatch.setattr("flaskr.auth.datetime", MockDatetime())

    ips = "10.0.0.1", "10.0.0.2"
    # Register a user
    response = client.post(
        url_for("auth.register"),
        data=generate_registration_postdata(1),
        environ_base={"REMOTE_ADDR": ips[0]},
    )
    # Success
    assert response.status_code == 302
    # Can't register right after registering
    assert does_ip_exceed_registration_rate_limit(ips[0])
    assert not does_ip_exceed_registration_rate_limit(ips[1])
    # Can't register until right before delay
    MockDatetime.now.return_value += delay - second
    assert does_ip_exceed_registration_rate_limit(ips[0])
    assert not does_ip_exceed_registration_rate_limit(ips[1])
    # Can register right after delay
    MockDatetime.now.return_value += 2 * second
    assert not does_ip_exceed_registration_rate_limit(ips[0])
    assert not does_ip_exceed_registration_rate_limit(ips[1])


def generate_post_postdata(index):
    return {
        "title": f"title{index}",
        "body": f"body{index}",
        "tags": "",
        "file": (BytesIO(b""), ""),
        "g-recaptcha-response": "123",
    }


@pytest.mark.usefixtures("recaptcha_always_passes")
def test_posting_checks_rate_limit(client, auth, monkeypatch):
    auth.login()
    url = url_for("blog.create")
    error = "You must wait a little before posting again with this user"
    mock_check_rate_limit = MagicMock(return_value=True)
    monkeypatch.setattr(
        "flaskr.blog.does_user_exceed_post_rate_limit", mock_check_rate_limit
    )
    response = client.post(url, data=generate_post_postdata(1))
    assert response.status_code == 200
    assert error in response.data.decode()
    assert mock_check_rate_limit.called_once_with(1)

    mock_check_rate_limit.return_value = False
    response = client.post(url, data=generate_post_postdata(2))
    assert response.status_code == 302


def test_posting_rate_limit_checker_firstpost(app):
    """User with no posts never exceeds rate limit"""
    assert not does_user_exceed_post_rate_limit(1234)


@pytest.mark.usefixtures("recaptcha_always_passes")
def test_posting_rate_limit_checker_delay(client, app, monkeypatch):
    now = datetime(2030, 2, 3, tzinfo=timezone.utc)
    delay = timedelta(seconds=37)
    second = timedelta(seconds=1)
    app.config["POSTING_RATE_LIMIT_SECONDS"] = delay.total_seconds()
    mock_now = MagicMock(return_value=now)

    class MockDatetime:
        now = mock_now

    monkeypatch.setattr("flaskr.blog.datetime", MockDatetime())

    create_post(1, "title", "body", [], b"", created=now)
    # Can't post right after posting
    assert does_user_exceed_post_rate_limit(1)
    assert not does_user_exceed_post_rate_limit(2)
    # Can't post until right before delay
    MockDatetime.now.return_value += delay - 1 * second
    assert does_user_exceed_post_rate_limit(1)
    assert not does_user_exceed_post_rate_limit(2)
    # Can post right after delay
    MockDatetime.now.return_value += 2 * second
    assert not does_user_exceed_post_rate_limit(1)
    assert not does_user_exceed_post_rate_limit(2)


def generate_comment_postdata(index):
    return {
        "body": f"body{index}",
        "g-recaptcha-response": "123",
    }


@pytest.mark.usefixtures("recaptcha_always_passes")
def test_commenting_checks_rate_limit(client, auth, monkeypatch):
    auth.login()
    url = url_for("blog.new_comment", post_id=1)
    error = "You must wait a little before commenting again with this user"
    mock_check_rate_limit = MagicMock(return_value=True)
    monkeypatch.setattr(
        "flaskr.blog.comments.does_user_exceed_comment_rate_limit",
        mock_check_rate_limit,
    )
    response = client.post(url, data=generate_comment_postdata(1))
    assert response.status_code == 200
    assert error in response.data.decode()
    assert mock_check_rate_limit.called_once_with(1)

    mock_check_rate_limit.return_value = False
    response = client.post(url, data=generate_comment_postdata(2))
    assert response.status_code == 302


def test_commenting_rate_limit_checker_firstcomment(app):
    """User with no comments never exceeds rate limit"""
    assert not does_user_exceed_comment_rate_limit(1234)


@pytest.mark.usefixtures("recaptcha_always_passes")
def test_commenting_rate_limit_checker_delay(client, app, monkeypatch):
    now = datetime(2030, 2, 3, tzinfo=timezone.utc)
    delay = timedelta(seconds=37)
    second = timedelta(seconds=1)
    app.config["COMMENTING_RATE_LIMIT_SECONDS"] = delay.total_seconds()
    mock_now = MagicMock(return_value=now)

    class MockDatetime:
        now = mock_now

    monkeypatch.setattr("flaskr.blog.comments.datetime", MockDatetime())

    create_comment(1, 1, "body", created=now)
    # Can't comment right after commenting
    assert does_user_exceed_comment_rate_limit(1)
    assert not does_user_exceed_comment_rate_limit(2)
    # Can't comment until right before delay
    MockDatetime.now.return_value += delay - 1 * second
    assert does_user_exceed_comment_rate_limit(1)
    assert not does_user_exceed_comment_rate_limit(2)
    # Can comment right after delay
    MockDatetime.now.return_value += 2 * second
    assert not does_user_exceed_comment_rate_limit(1)
    assert not does_user_exceed_comment_rate_limit(2)
