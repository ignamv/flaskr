from time import sleep
import os
from unittest.mock import MagicMock
import pytest
from flask import url_for
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from flaskr.recaptcha import validate_recaptcha_response
from flaskr import create_app


def click_recaptcha(webdriver):
    iframe = webdriver.find_element(By.CSS_SELECTOR,
                                    'iframe[title="reCAPTCHA"]')
    webdriver.switch_to.frame(iframe)
    def find_checkboxes(webdriver):
        return webdriver.find_elements(By.CLASS_NAME, 
                                       'recaptcha-checkbox-border')
    checkbox, = WebDriverWait(webdriver, timeout=5).until(find_checkboxes)
    checkbox.click()
    webdriver.switch_to.default_content()


@pytest.mark.slow
def test_recaptcha_e2e(browser):
    webdriver = browser
    webdriver.get(url_for('recaptcha.recaptcha_test', always_pass=True,
                          _external=True))
    assert webdriver.title == 'reCAPTCHA demo: Simple page'
    click_recaptcha(webdriver)
    sleep(0.5)
    submit = webdriver.find_element(By.XPATH, '//input[@type="submit"]')
    submit.click()
    def valid_text(webdriver):
        return webdriver.find_element(By.ID, 'valid').text
    def in_correct_page(webdriver):
        return valid_text(webdriver) != ''
    WebDriverWait(webdriver, timeout=9).until(in_correct_page)
    assert valid_text(webdriver) == 'Valid'


@pytest.mark.parametrize('valid', (False, True))
def test_recaptcha_invalid_response(client, valid):
    data = {'g-recaptcha-response': '03AGdBq24cX4nu_RoJTUmJDnwTyff8yxwY0--wrS-kcQB-w6rGRPzUkeyv0lBwH20djCEehTTu39tvITBrL7louxb3QltefCAeDJAP3CuHzBjlOoKZI6GpeFdUiGS9kxxQU47s-JdryJ-JVTvzIGlWoJAabnyl2LCIrYftve5sq5LYWZkS46VGrBOwW4nl945g7e7saRwzqEhIkfhVrIi3LOE-SweW1W72V5-84-tLo-LAmLVQLW4UOepeTPoJLQhwLxicbvM42K1-l5YVpWFMGLXdjZXdjA2WqgxNpXaX--3LEfEgGqYlI6Ir1zHHuWaUO45k1GBZNJ8NtkQgFzBh5JA1-58DW0KLF1YcJgrfIZS7RQlfuQHhRS2gid2dy_8HdmtyeKPr3R9VN2NxYrQUCqAY15_yED0HKzeUtPM8u6w-VTJ3FdyZ3QreltaYWPEuwrPtu0yPAGfW25C-_oYoDXqrknQyG5a8OdZVtuelX14A6IeiC4wCB89Oa_UX9DO3y0NJ6tfxLvWP'}
    response = client.post(url_for('recaptcha.recaptcha_test',
        always_pass=valid), data=data).data.decode()
    assert ('Invalid' not in response) == valid
    assert ('Valid' in response) == valid


@pytest.mark.parametrize('invalidjson', ('inv true', 'inv false', '{}',
                                         '{"success": "yes"}'))
def test_validate_recaptcha_rejects_invalid_json(monkeypatch, invalidjson):
    mock_post = MagicMock(return_value=invalidjson)
    monkeypatch.setattr('flaskr.recaptcha.requests.post', mock_post)
    with pytest.raises(Exception):
        validate_recaptcha_response('response', 'secret')

@pytest.mark.parametrize(('empty_response', 'success'), [
    (False, False), (False, True), (True, True)])
def test_validate_recaptcha_mocking_network(monkeypatch, empty_response, success):
    response = (
        '03AGdBq24cX4nu_RoJTUmJDnwTyff8yxwY0--wrS-kcQB-w6rGRPzUkeyv0lBwH20d'
        'jCEehTTu39tvITBrL7louxb3QltefCAeDJAP3CuHzBjlOoKZI6GpeFdUiGS9kxxQU4'
        '7s-JdryJ-JVTvzIGlWoJAabnyl2LCIrYftve5sq5LYWZkS46VGrBOwW4nl945g7e7s'
        'aRwzqEhIkfhVrIi3LOE-SweW1W72V5-84-tLo-LAmLVQLW4UOepeTPoJLQhwLxicbv'
        'M42K1-l5YVpWFMGLXdjZXdjA2WqgxNpXaX--3LEfEgGqYlI6Ir1zHHuWaUO45k1GBZ'
        'NJ8NtkQgFzBh5JA1-58DW0KLF1YcJgrfIZS7RQlfuQHhRS2gid2dy_8HdmtyeKPr3R'
        '9VN2NxYrQUCqAY15_yED0HKzeUtPM8u6w-VTJ3FdyZ3QreltaYWPEuwrPtu0yPAGfW'
        '25C-_oYoDXqrknQyG5a8OdZVtuelX14A6IeiC4wCB89Oa_UX9DO3y0NJ6tfxLvWP'
    ) * (not empty_response)
    secretkey = '6LeIxAcTAAAAAGG-vFI1TNRWXMZNFUOJJ4WifJWe'
    class MockResponse:
        text = f'''{{
  "success": {str(success).lower()},
  "challenge_ts": "2022-02-17T05:49:59Z",
  "hostname": "testkey.google.com"
}}'''
    mock_post = MagicMock(return_value=MockResponse())
    monkeypatch.setattr('flaskr.recaptcha.requests.post', mock_post)
    assert validate_recaptcha_response(response, secretkey) == success * (not empty_response)
    if not empty_response:
        mock_post.assert_called_once()
        assert mock_post.call_args.args == (
            'https://www.google.com/recaptcha/api/siteverify', )
        postdata = mock_post.call_args.kwargs['data']
        assert postdata['response'] == response
        assert postdata['secret'] == secretkey


def test_recaptcha_blueprint_validates_config_on_startup(temporary_working_directory):
    instance = temporary_working_directory.joinpath('instance')
    instance.mkdir()
    instance.joinpath('config.py').write_text('')
    app = create_app()
    with app.app_context():
        with pytest.raises(AssertionError):
            app.test_client().get('/hello')
