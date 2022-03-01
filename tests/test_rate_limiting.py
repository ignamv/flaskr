import pytest
from unittest.mock import MagicMock
from flask import url_for
from flaskr.auth_db import register_user
from flaskr.auth import does_ip_exceed_registration_rate_limit
from datetime import datetime, timezone


def generate_registration_postdata(index):
    return {
        "username": f"user{index}",
        "password": f"password{index}",
        "g-recaptcha-response": "123",
    }


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
    print(response.data.decode())
    assert response.status_code == 302

    assert does_ip_exceed_registration_rate_limit(ips[0])
    assert not does_ip_exceed_registration_rate_limit(ips[1])
    # After some time passes, I can also register from the original IP
    now = datetime(2030, 2, 4, tzinfo=timezone.utc)
    MockDatetime.now.return_value = now
    assert not does_ip_exceed_registration_rate_limit(ips[0])
    assert not does_ip_exceed_registration_rate_limit(ips[1])
