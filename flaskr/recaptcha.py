import requests
import json
from flask import Blueprint, request, render_template, current_app

bp = Blueprint("recaptcha", __name__)


def validate_recaptcha_response(response, secretkey):
    if not response:
        # User did not click the captcha checkbox
        # This still passes verification when using Google's unit testing keys
        # We can force rejection here to be able to test that the captcha is
        # verified
        return False
    validation = json.loads(
        requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "response": response,
                "secret": secretkey,
            },
        ).text
    )
    ret = validation["success"]
    assert isinstance(ret, bool)
    print(f"Validated {response!r} as {ret} with {secretkey}")
    return ret


@bp.route("/recaptcha_test", methods=("GET", "POST"))
def recaptcha_test():
    try:
        always_pass = request.args["always_pass"]
    except:
        always_pass = request.form.get("always_pass", "False")
    always_pass = {"False": False, "True": True}[always_pass]
    if always_pass:
        # Always verifies as good with keys for unit testing
        # From https://developers.google.com/recaptcha/docs/faq
        sitekey = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
        secretkey = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"
    else:
        sitekey = current_app.config["RECAPTCHA_SITEKEY"]
        secretkey = current_app.config["RECAPTCHA_SECRETKEY"]
    valid = None
    if request.method == "POST":
        valid = validate_recaptcha_response(
            request.form["g-recaptcha-response"], secretkey
        )
    return render_template(
        "recaptcha.html", valid=valid, sitekey=sitekey, always_pass=always_pass
    )


@bp.before_app_first_request
def check_recaptcha_keys():
    print(dict(current_app.config))
    assert "RECAPTCHA_SITEKEY" in current_app.config
    assert "RECAPTCHA_SECRETKEY" in current_app.config
