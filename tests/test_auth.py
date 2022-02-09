import pytest
from flask import g, session
from flaskr.db import get_db
from flaskr.auth_db import register_user


login_url = "http://localhost/auth/login"


def test_register(client, app):
    assert client.get("/auth/register").status_code == 200
    response = client.post("/auth/register", data={"username": "a", "password": "pw"})
    assert login_url == response.headers["Location"]

    with app.app_context():
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
def test_register_validate_input(client, username, password, message):
    response = client.post(
        "/auth/register", data={"username": username, "password": password}
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
    register_user("example1", "samepassword")
    register_user("example2", "samepassword")
    hashes = {
        row[0]
        for row in get_db()
        .execute('SELECT password FROM user WHERE username LIKE "example%"')
        .fetchall()
    }
    assert len(hashes) == 2
