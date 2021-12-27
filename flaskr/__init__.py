import os

from flask import Flask


def create_app(test_config=None):
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev", DATABASE=os.path.join(app.instance_path, "flaskr.sqlite")
    )

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    # A simple page that says hello
    @app.route("/hello")
    def hello():
        return "Hello world"

    from .db import init_app

    init_app(app)
    from .auth import bp

    app.register_blueprint(bp)

    return app
