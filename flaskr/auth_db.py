from flaskr.db import get_db
from werkzeug.security import generate_password_hash, check_password_hash


class WrongPasswordException(Exception):
    pass


def register_user(username, password):
    db = get_db()
    db.execute(
        'INSERT INTO user (username, password) VALUES (?, ?)',
        (username, generate_password_hash(password)),
    )
    db.commit()


def check_login_credentials(username, password):
    db = get_db()
    user = db.execute('SELECT id, username, password FROM user WHERE username = ?',
                      (username,)).fetchone()
    if user is None:
        raise KeyError(username)
    elif not check_password_hash(user['password'], password):
        raise WrongPasswordException()
    return user


def load_user(user_id):
    return get_db().execute('SELECT * FROM user WHERE id = ?',
                            (user_id,)).fetchone()
