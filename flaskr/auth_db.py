from datetime import datetime, timezone
from flaskr.db import get_db, parse_timestamp_utc
from werkzeug.security import generate_password_hash, check_password_hash


class WrongPasswordException(Exception):
    pass


def register_user(username, password, registration_ip, registration_time):
    db = get_db()
    db.execute(
        "INSERT INTO user (username, password, registration_ip, registration_time) VALUES (?, ?, ?, ?)",
        (
            username,
            generate_password_hash(password),
            registration_ip,
            registration_time,
        ),
    )
    db.commit()


def check_login_credentials(username, password):
    db = get_db()
    user = db.execute(
        "SELECT id, username, password FROM user WHERE username = ?", (username,)
    ).fetchone()
    if user is None:
        raise KeyError(username)
    elif not check_password_hash(user["password"], password):
        raise WrongPasswordException()
    return user


def load_user(user_id):
    return get_db().execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()


def get_last_registration_date_for_ip(ip):
    row = (
        get_db()
        .execute(
            "SELECT registration_time FROM user WHERE registration_ip == ?"
            " ORDER BY registration_time DESC LIMIT 1",
            (ip,),
        )
        .fetchone()
    )
    if row is not None:
        return row[0]
    return None
