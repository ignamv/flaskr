import requests
import json
from flask import Blueprint, request, render_template, current_app
from contextlib import contextmanager, nullcontext
bp = Blueprint('recaptcha', __name__)


def generate_recaptcha_html(sitekey=None):
    if sitekey is None:
        sitekey = current_app.config['RECAPTCHA_SITEKEY']
    return f'''
        <script src="https://www.google.com/recaptcha/api.js" async defer>
        </script>
        <div class="g-recaptcha" data-sitekey="{sitekey}"></div>
    '''


def validate_recaptcha_response(response, secretkey=None):
    if secretkey is None:
        secretkey = current_app.config['RECAPTCHA_SECRETKEY']
    if not response:
        # User did not click the captcha checkbox
        # This still passes verification when using Google's unit testing keys
        # We can force rejection here to be able to test that the captcha is
        # verified
        return False
    validation = json.loads(requests.post(
        'https://www.google.com/recaptcha/api/siteverify', data={
            'response': response,
            'secret': secretkey,
            }
    ).text)
    ret = validation['success']
    assert isinstance(ret, bool)
    return ret


@contextmanager
def recaptcha_always_passes_context():
    """
    Within this block, captchas can be roboclicked and always verify as good

    Uses the unit testing keys from 
    https://developers.google.com/recaptcha/docs/faq
    """
    testing_config = {
        'RECAPTCHA_SITEKEY': '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI',
        'RECAPTCHA_SECRETKEY': '6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe',
    }
    original_config = {k: current_app.config[k] for k in testing_config}
    current_app.config.update(testing_config)
    yield
    current_app.config.update(original_config)


@bp.route('/recaptcha_test', methods=('GET', 'POST'))
def recaptcha_test():
    try:
        always_pass = request.args['always_pass']
    except:
        always_pass = request.form.get('always_pass', 'False')
    always_pass = {'False': False, 'True': True}[always_pass]
    ctx = recaptcha_always_passes_context() if always_pass else nullcontext()
    valid = None
    with ctx:
        recaptcha_html = generate_recaptcha_html()
        if request.method == 'POST':
            valid = validate_recaptcha_response(
                request.form['g-recaptcha-response'])
        return render_template('recaptcha.html', valid=valid,
                               recaptcha_html=recaptcha_html,
                               always_pass=always_pass)


@bp.before_app_first_request
def check_recaptcha_keys():
    assert 'RECAPTCHA_SITEKEY' in current_app.config
    assert 'RECAPTCHA_SECRETKEY' in current_app.config
