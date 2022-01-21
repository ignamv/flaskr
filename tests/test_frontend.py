import re
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from flask import url_for
from werkzeug.routing import RequestRedirect, MethodNotAllowed, NotFound


@pytest.fixture()
def browser(live_server):
    ret = webdriver.Firefox()
    ret.get(url_for("index", _external=True))
    yield ret
    ret.quit()


class PageObject(object):
    def __init__(self, webdriver):
        self.webdriver = webdriver
        self.assert_in_correct_page()

    def assert_in_correct_page(self):
        match = re.match(self.title_regex, self.webdriver.title)
        assert match is not None, (
            f'Title "{self.webdriver.title}" does not' f' match "{self.title_regex}"'
        )

    def go_home(self):
        self.webdriver.find_element(By.ID, "flaskr_logo").click()
        return HomePage(self.webdriver)


class HomePage(PageObject):
    title_regex = "Latest posts - Flaskr$"

    def register(self):
        self.webdriver.find_element(By.ID, "register").click()
        return RegisterPage(self.webdriver)

    def logout(self):
        self.webdriver.find_element(By.ID, "logout").click()
        return HomePage(self.webdriver)

    def newpost(self):
        self.webdriver.find_element(By.ID, "newpost").click()
        return NewPostPage(self.webdriver)

    def get_username(self):
        try:
            return self.webdriver.find_element(By.ID, "username").text
        except NoSuchElementException:
            return None


class RegisterPage(PageObject):
    title_regex = "Register - Flaskr$"

    def register(self, username, password):
        self.webdriver.find_element(By.NAME, "username").send_keys(username)
        self.webdriver.find_element(By.NAME, "password").send_keys(password)
        self.webdriver.find_element(By.ID, "submit_registration").click()
        return LoginPage(self.webdriver)


class LoginPage(PageObject):
    title_regex = "Log In - Flaskr$"

    def login(self, username, password):
        self.webdriver.find_element(By.NAME, "username").send_keys(username)
        self.webdriver.find_element(By.NAME, "password").send_keys(password)
        self.webdriver.find_element(By.ID, "submit_login").click()
        return HomePage(self.webdriver)


def clear_and_send_keys(element, keys):
    element.clear()
    element.send_keys(keys)


class NewOrEditPostPage(PageObject):
    def submit(self, title, body, tags):
        clear_and_send_keys(self.webdriver.find_element(By.NAME, "title"), title)
        clear_and_send_keys(self.webdriver.find_element(By.NAME, "body"), body)
        clear_and_send_keys(
            self.webdriver.find_element(By.NAME, "tags"), ",".join(tags)
        )
        self.webdriver.find_element(By.ID, "submit_post").click()

    def submit_good(self, title, body, tags):
        self.submit(title, body, tags)
        return PostPage(self.webdriver)

    def submit_bad(self, title, body, tags):
        self.submit(title, body, tags)
        return self.__class__(self.webdriver)


def find_posts(webdriver):
    return [
        Post(webdriver, elem)
        for elem in webdriver.find_elements(By.XPATH, '//article[@class="post"]')
    ]


class Post(object):
    def __init__(self, webdriver, element):
        self.webdriver = webdriver
        self.element = element

    def get_title(self):
        return self.element.find_element(By.CLASS_NAME, "post_title").text

    def get_body(self):
        return self.element.find_element(By.CLASS_NAME, "body").text

    def get_tags(self):
        return {elem.text for elem in self.element.find_elements(By.CLASS_NAME, "tag")}

    def edit(self):
        self.element.find_element(By.ID, "edit").click()
        return UpdatePostPage(self.webdriver)


class PostPage(PageObject):
    def assert_in_correct_page(self):
        assert (
            len(self.webdriver.find_elements(By.CLASS_NAME, "post_title")) == 1
        ), "Post page should have exactly one post"

    def get_post(self):
        return find_posts(self.webdriver)[0]


class NewPostPage(NewOrEditPostPage):
    title_regex = "Write New Entry - Flaskr$"


class UpdatePostPage(NewOrEditPostPage):
    title_regex = "Update Entry - Flaskr$"


class TestTour1:
    def register(self):
        homepage = HomePage(self.browser)
        # Start logged out
        assert homepage.get_username() is None
        # Register
        registerpage = homepage.register()
        self.user, self.password = "selenium", "seleniumpw"
        return registerpage.register(self.user, self.password)

    def login(self, loginpage):
        homepage = loginpage.login(self.user, self.password)
        # Should be logged in
        assert homepage.get_username() == self.user
        return homepage

    def create_post(self, homepage):
        newpostpage = homepage.newpost()
        self.title, self.body = "self.title selenium", "self.body selenium"
        self.tags = {"sele", "nium"}
        # Try with missing title or body
        newpostpage.submit_bad("", self.body, self.tags)
        newpostpage.submit_bad(self.title, "", self.tags)
        return newpostpage.submit_good(self.title, self.body, self.tags)

    def check_post(self, post):
        assert post.get_title() == self.title
        assert post.get_body() == self.body
        assert post.get_tags() == self.tags

    def edit_post(self, post):
        updatepage = post.edit()
        self.title, self.body = "edited title selenuim", "edited body selenuim"
        self.tags = {"selen", "ium"}
        # Try with missing self.title or self.body
        updatepage.submit_bad("", self.body, self.tags)
        updatepage.submit_bad(self.title, "", self.tags)
        return updatepage.submit_good(self.title, self.body, self.tags)

    def logout(self, homepage):
        homepage = homepage.logout()
        assert homepage.get_username() is None

    def test_register_post(self, browser):
        self.browser = browser
        loginpage = self.register()
        homepage = self.login(loginpage)
        postpage = self.create_post(homepage)
        post = postpage.get_post()
        self.check_post(post)
        postpage = self.edit_post(post)
        post = postpage.get_post()
        self.check_post(post)
        homepage = postpage.go_home()
        self.logout(homepage)
