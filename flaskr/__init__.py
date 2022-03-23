import os

from flask import Flask, current_app
from markupsafe import Markup
from bleach import Cleaner
from bleach.linkifier import LinkifyFilter
from bleach.sanitizer import ALLOWED_TAGS
from markdown import markdown


def render_sanitize_markdown(markdown_markup):
    cleaner = Cleaner(tags=ALLOWED_TAGS + ["p"], filters=[LinkifyFilter])
    html = cleaner.clean(markdown(markdown_markup))
    return Markup(html)


def summarize(markdown, single_post):
    max_length = current_app.config["SUMMARY_LENGTH"]
    if len(markdown) > max_length and not single_post:
        return markdown[:max_length] + "[...]"
    return markdown


def create_app(test_config=None):
    # Create and configure the app
    app = Flask(
        __name__,
        instance_relative_config=True,
        instance_path=os.path.join(os.getcwd(), "instance"),
    )
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "flaskr.sqlite"),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        REGISTRATION_RATE_LIMIT_SECONDS=1800,
        POSTING_RATE_LIMIT_SECONDS=300,
        COMMENTING_RATE_LIMIT_SECONDS=120,
        SUMMARY_LENGTH=300,
    )

    if test_config is not None:
        app.config.from_mapping(test_config)
    prefix = "FLASKR_"
    app.config.from_mapping(
        {
            k.partition(prefix)[2]: v
            for k, v in os.environ.items()
            if k.startswith(prefix)
        }
    )

    app.jinja_env.globals["debug"] = app.debug
    app.jinja_env.filters["render_sanitize_markdown"] = render_sanitize_markdown
    app.jinja_env.filters["summarize"] = summarize
    if not app.testing and not app.config["SECRET_KEY"]:
        raise KeyError("SECRET_KEY")

    os.makedirs(app.instance_path, exist_ok=True)

    # A simple page that says hello
    @app.route("/hello")
    def hello():
        return "Hello world"

    from .db import init_app

    init_app(app)
    from .auth import bp as auth_bp

    app.register_blueprint(auth_bp)
    from .blog import bp as blog_bp

    app.register_blueprint(blog_bp)
    from .recaptcha import bp as recaptcha_bp

    app.register_blueprint(recaptcha_bp)
    app.add_url_rule("/", endpoint="index")

    return app
