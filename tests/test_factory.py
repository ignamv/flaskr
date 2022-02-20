import os
import pytest
from flaskr import create_app


def test_config(temporary_working_directory):
    instance = temporary_working_directory.joinpath('instance')
    instance.mkdir()
    instance.joinpath('config.py').write_text('')
    assert not create_app().testing
    assert create_app({'TESTING': True}).testing


def test_hello(client):
    response = client.get('/hello')
    assert response.data.decode() == 'Hello world'


def test_production_requires_config_file(temporary_working_directory):
    # Production app requires config
    with pytest.raises(FileNotFoundError):
        create_app()
