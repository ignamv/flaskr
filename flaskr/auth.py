import functools
from sqlite3 import IntegrityError

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    current_app,
)
from flaskr.db import get_db
from flaskr.auth_db import (
    register_user,
    check_login_credentials,
    WrongPasswordException,
    load_user,
)
from .recaptcha import validate_recaptcha_response, generate_recaptcha_html

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        recaptcha_response = request.form["g-recaptcha-response"]
        error = None

        if not username:
            error = "Username is required"
        elif not password:
            error = "Password is required"
        elif not recaptcha_response or not validate_recaptcha_response(
            recaptcha_response
        ):
            error = "Invalid captcha"
        if error is None:
            try:
                register_user(username, password)
            except IntegrityError:
                error = f"User {username} is already registered"
            else:
                return redirect(url_for("auth.login"))

        flash(error)

    recaptcha_html = generate_recaptcha_html()
    return render_template("auth/register.html", recaptcha=recaptcha_html)


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        error = None
        try:
            user = check_login_credentials(username, password)
        except KeyError:
            error = "Incorrect username"
        except WrongPasswordException:
            error = "Incorrect password"

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("index"))

        flash(error)

    return render_template("auth/login.html")


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = load_user(user_id)


def get_user_id():
    if g.user is None:
        return -1
    else:
        return g.user["id"]


# TODO: fix CSRF
@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(**kwargs)

    return wrapped_view
