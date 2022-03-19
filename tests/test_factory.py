import os
import pytest
from flaskr import create_app


def test_config(temporary_working_directory):
    assert create_app({"TESTING": True}).testing


def test_hello(client):
    response = client.get("/hello")
    assert response.data.decode() == "Hello world"


def test_production_requires_config_environ(temporary_working_directory, environ):
    """Production app requires config in environment variables"""
    envvars = {
        "FLASKR_SECRET_KEY": "123123123",
        "FLASKR_RECAPTCHA_SITEKEY": "sitekey",
        "FLASKR_RECAPTCHA_SECRETKEY": "secretkey",
        "FLASKR_DUMMY": "justkidding",
    }
    for k in envvars:
        if k in environ:
            del environ[k]
    with pytest.raises(KeyError):
        create_app()
    environ.update(envvars)
    app = create_app()
    assert app.config["SECRET_KEY"] == envvars["FLASKR_SECRET_KEY"]
    assert app.config["RECAPTCHA_SITEKEY"] == envvars["FLASKR_RECAPTCHA_SITEKEY"]
    assert app.config["RECAPTCHA_SECRETKEY"] == envvars["FLASKR_RECAPTCHA_SECRETKEY"]
    assert app.config["DUMMY"] == envvars["FLASKR_DUMMY"]
