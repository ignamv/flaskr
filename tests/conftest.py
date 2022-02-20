import os
import tempfile
from selenium import webdriver
import pytest
from flask import url_for
from flaskr import create_app
from flaskr.db import get_db, init_db

with open(os.path.join(os.path.dirname(__file__), "data.sql"), "rb") as fd:
    _data_sql = fd.read().decode("utf8")


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()

    app = create_app(
        {
            "TESTING": True,
            "DATABASE": db_path,
        }
    )

    with app.app_context():
        init_db()
        get_db().executescript(_data_sql)
        yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


class AuthActions(object):
    def __init__(self, client):
        self._client = client

    def login(self, username="test", password=None):
        if password is None:
            password = {"test": "test", "other": "pw2"}[username]
        return self._client.post(
            "/auth/login", data={"username": username, "password": password}
        )

    def logout(self):
        return self._client.get("/auth/logout")


@pytest.fixture
def auth(client):
    return AuthActions(client)


def pytest_addoption(parser):
    parser.addoption("--production-url", help="url for production server to test")


@pytest.fixture
def production_url(pytestconfig):
    url = pytestconfig.getoption("--production-url")
    if not url:
        pytest.skip()
    return url


@pytest.fixture()
def browser(live_server):
    ret = webdriver.Firefox()
    ret.get(url_for("index", _external=True))
    yield ret
    ret.quit()


@pytest.fixture
def temporary_working_directory(tmp_path):
    original_working_directory = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_working_directory)
