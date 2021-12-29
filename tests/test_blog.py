import pytest
from flaskr.db import get_db


def test_index(client, auth):
    response = client.get('/')
    assert b'Log In' in response.data
    assert b'Register' in response.data

    auth.login()
    response = client.get('/')
    strings = (
        b'Log Out',
        b'test title',
        b'by test',
        b'on 2018-01-01',
        b'test\nbody',
        b'href="/1/update"',
    )
    for string in strings:
        assert string in response.data


@pytest.mark.parametrize('path', ('/create', '/1/update', '/1/delete'))
def test_login_required(client, auth, path):
    response = client.post(path)
    print(response.headers)
    print(response.data)
    assert response.headers['Location'] == 'http://localhost/auth/login'
