import os

from flask import Flask


def create_app(test_config=None):
    # Create and configure the app
    app = Flask(
        __name__,
        instance_relative_config=True,
        instance_path=os.path.join(os.getcwd(), "instance"),
    )
    app.config.from_mapping(
        SECRET_KEY="dev", DATABASE=os.path.join(app.instance_path, "flaskr.sqlite")
    )
    app.jinja_env.globals["debug"] = app.debug

    # Load the instance config, if it exists, when not testing
    app.config.from_pyfile("config.py")
    if test_config is not None:
        app.config.from_mapping(test_config)

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
    app.add_url_rule("/", endpoint="index")

    return app
