from datetime import datetime
from unittest.mock import MagicMock
import pytest
from flask import g, session, url_for
from flaskr.db import get_db
from flaskr.auth_db import register_user


login_url = "http://localhost/auth/login"


def test_register(client, app, monkeypatch):
    postdata = {"username": "a", "password": "pw", "g-recaptcha-response": ""}
    register_url = url_for("auth.register", _external=True)

    response = client.get(register_url)
    assert 'src="https://www.google.com/recaptcha/api.js"' in response.data.decode()
    assert response.status_code == 200

    response = client.post(register_url, data=postdata)
    assert response.status_code == 200
    assert "Invalid captcha" in response.data.decode()

    postdata["g-recaptcha-response"] = "123"
    mock_validate_captcha_response = MagicMock(return_value=True)
    monkeypatch.setattr(
        "flaskr.auth.validate_recaptcha_response", mock_validate_captcha_response
    )
    response = client.post(register_url, data=postdata)
    mock_validate_captcha_response.assert_called_once()
    assert mock_validate_captcha_response.call_args.args[0] == "123"
    assert login_url == response.headers["Location"]

    assert (
        get_db().execute("SELECT * FROM user WHERE username = 'a'").fetchone()
        is not None
    )


@pytest.mark.parametrize(
    ("username", "password", "message"),
    (
        ("", "", "Username is required"),
        ("a", "", "Password is required"),
        ("test", "test", "already registered"),
    ),
)
def test_register_validate_input(client, username, password, message, monkeypatch):
    monkeypatch.setattr(
        "flaskr.auth.validate_recaptcha_response", MagicMock(return_value=True)
    )
    response = client.post(
        "/auth/register",
        data={
            "username": username,
            "password": password,
            "g-recaptcha-response": "123",
        },
    )
    assert message in response.data.decode()


def test_login(client, auth):
    assert client.get("/auth/login").status_code == 200
    response = auth.login()
    assert response.headers["Location"] == "http://localhost/"

    with client:
        client.get("/")
        assert session["user_id"] == 1
        assert g.user["username"] == "test"


@pytest.mark.parametrize(
    ("username", "password", "message"),
    (
        ("a", "test", "Incorrect username"),
        ("test", "a", "Incorrect password"),
    ),
)
def test_login_validate_input(auth, username, password, message):
    response = auth.login(username, password)
    assert message in response.data.decode()


def test_logout(client, auth):
    auth.login()
    with client:
        auth.logout()
        assert "user_id" not in session


def test_password_hash_unique(app):
    """Ensure password hash is salted with a unique salt"""
    ip = "10.0.0.1"
    time = datetime.now()
    register_user("example1", "samepassword", ip, time)
    register_user("example2", "samepassword", ip, time)
    hashes = {
        row[0]
        for row in get_db()
        .execute('SELECT password FROM user WHERE username LIKE "example%"')
        .fetchall()
    }
    assert len(hashes) == 2
