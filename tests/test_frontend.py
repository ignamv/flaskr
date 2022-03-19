import re
import pytest
import attr
from time import sleep
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)
from flask import url_for
from werkzeug.routing import RequestRedirect, MethodNotAllowed, NotFound

from flaskr.recaptcha import recaptcha_always_passes_context
from test_recaptcha import click_recaptcha


def element_is_stale(element):
    try:
        element.is_enabled()
    except StaleElementReferenceException:
        return True
    return False


class PageObject(object):
    def __init__(self, webdriver):
        WebDriverWait(webdriver, timeout=2).until(self.in_correct_page)
        self.webdriver = webdriver

    def refresh(self):
        self.webdriver.get(self.webdriver.current_url)

    @property
    def errors(self):
        return [
            elem.text for elem in self.webdriver.find_elements(By.CLASS_NAME, "flash")
        ]

    def in_correct_page(self, webdriver):
        match = re.match(self.title_regex, webdriver.title)
        return match is not None

    def go_home(self):
        self.webdriver.find_element(By.ID, "flaskr_logo").click()
        return HomePage(self.webdriver)

    def register(self):
        self.webdriver.find_element(By.ID, "register").click()
        return RegisterPage(self.webdriver)

    def logout(self):
        self.webdriver.find_element(By.ID, "logout").click()
        return HomePage(self.webdriver)

    def get_username(self):
        try:
            return self.webdriver.find_element(By.ID, "username").text
        except NoSuchElementException:
            return None

    def search(self, query):
        box = self.webdriver.find_element(By.ID, "searchbox")
        box.send_keys(query)
        box.send_keys(Keys.RETURN)
        return ResultsPage(self.webdriver, query)

    def browse_tags(self):
        self.webdriver.find_element(By.ID, "browse_tags").click()
        return TagsPage(self.webdriver)


class ResultsPage(PageObject):
    def __init__(self, webdriver, searchquery):
        self.title_regex = f"Search.*{re.escape(searchquery)}.*Flaskr$"
        super(ResultsPage, self).__init__(webdriver)

    @property
    def posts(self):
        return find_posts(self.webdriver)


class TagPage(PageObject):
    def __init__(self, webdriver, tag):
        self.title_regex = f"Posts tagged with.*{re.escape(tag)}.*Flaskr$"
        super(TagPage, self).__init__(webdriver)

    @property
    def posts(self):
        return find_posts(self.webdriver)


@attr.s
class Tag(object):
    name = attr.ib(type=str)
    count = attr.ib(type=int)
    webdriver = attr.ib(default=None, eq=False)
    element = attr.ib(default=None, eq=False)

    @classmethod
    def from_element(cls, webdriver, element):
        name, count = re.match(r"(.*) \((\d+)\)", element.text).groups()
        return cls(name, int(count), webdriver, element)

    def goto(self):
        self.element.click()
        return TagPage(self.webdriver, self.name)


class TagsPage(PageObject):
    title_regex = "Tags.*Flaskr$"

    @property
    def tags(self):
        return [
            Tag.from_element(self.webdriver, elem)
            for elem in self.webdriver.find_elements(By.CLASS_NAME, "tag")
        ]


class HomePage(PageObject):
    title_regex = "Latest posts - Flaskr$"

    def newpost(self):
        self.webdriver.find_element(By.ID, "newpost").click()
        return NewPostPage(self.webdriver)


class RegisterPage(PageObject):
    title_regex = "Register - Flaskr$"

    def register(self, username, password, recaptcha):
        username_field = self.webdriver.find_element(By.NAME, "username")
        clear_and_send_keys(username_field, username)
        clear_and_send_keys(self.webdriver.find_element(By.NAME, "password"), password)
        if recaptcha:
            click_recaptcha(self.webdriver)
        self.webdriver.find_element(By.ID, "submit_registration").click()
        if element_is_stale(username_field) and not self.in_correct_page(
            self.webdriver
        ):
            return LoginPage(self.webdriver)
        return self


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
    def submit(self, title, body, tags, recaptcha=False):
        title_field = self.webdriver.find_element(By.NAME, "title")
        clear_and_send_keys(title_field, title)
        clear_and_send_keys(self.webdriver.find_element(By.NAME, "body"), body)
        clear_and_send_keys(
            self.webdriver.find_element(By.NAME, "tags"), ",".join(tags)
        )
        if recaptcha:
            click_recaptcha(self.webdriver)
        self.webdriver.find_element(By.ID, "submit_post").click()
        if element_is_stale(title_field) and not self.in_correct_page(self.webdriver):
            return PostPage(self.webdriver)
        return self


class NewOrEditCommentPage(PageObject):
    def submit(self, body, recaptcha=False):
        body_field = self.webdriver.find_element(By.NAME, "body")
        clear_and_send_keys(body_field, body)
        if recaptcha:
            click_recaptcha(self.webdriver)
        self.webdriver.find_element(By.ID, "submit_comment").click()
        if element_is_stale(body_field) and not self.in_correct_page(self.webdriver):
            return PostPage(self.webdriver)
        return self


class NewCommentPage(NewOrEditCommentPage):
    title_regex = "New comment on .* - Flaskr"


class UpdateCommentPage(NewOrEditCommentPage):
    title_regex = "Update comment on .* - Flaskr"


def find_posts(webdriver):
    return [
        Post.from_element(webdriver, elem)
        for elem in webdriver.find_elements(By.XPATH, '//article[@class="post"]')
    ]


@attr.s
class Post(object):
    title = attr.ib()
    body = attr.ib()
    tags = attr.ib(default=None)
    webdriver = attr.ib(default=None, eq=False)
    element = attr.ib(default=None, eq=False)

    @classmethod
    def from_element(cls, webdriver, element):
        title = element.find_element(By.CLASS_NAME, "post_title").text
        body = element.find_element(By.TAG_NAME, "p").text
        tags_containers = element.find_elements(By.CLASS_NAME, "tags")
        if not tags_containers:
            tags = None
        else:
            tags = {
                elem.text
                for elem in tags_containers[0].find_elements(By.CLASS_NAME, "tag")
            }
        return cls(title, body, tags, webdriver, element)

    def edit(self):
        self.element.find_element(By.CLASS_NAME, "edit_post").click()
        return UpdatePostPage(self.webdriver)


@attr.s
class Comment(object):
    body = attr.ib()
    webdriver = attr.ib(default=None, eq=False)
    element = attr.ib(default=None, eq=False)

    @classmethod
    def from_element(cls, webdriver, element):
        body = element.find_element(By.CLASS_NAME, "body").text
        return cls(body, webdriver, element)

    def edit(self):
        self.element.find_element(By.CLASS_NAME, "edit_comment").click()
        return UpdateCommentPage(self.webdriver)


class PostPage(PageObject):
    def in_correct_page(self, webdriver):
        # Post page should have exactly one post
        return len(webdriver.find_elements(By.CLASS_NAME, "post_title")) == 1

    @property
    def post(self):
        return find_posts(self.webdriver)[0]

    @property
    def comments(self):
        return [
            Comment.from_element(self.webdriver, elem)
            for elem in self.webdriver.find_elements(By.CLASS_NAME, "comment")
        ]

    def new_comment(self):
        self.webdriver.find_element(By.ID, "new_comment").click()
        return NewCommentPage(self.webdriver)


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
        registerpage.register(self.user, "", False)
        registerpage.register("", self.password, False)
        registerpage.register(self.user, self.password, False)
        assert registerpage.errors == ["Invalid captcha"]
        with recaptcha_always_passes_context():
            self.live_server.stop()
            self.live_server.start()
            sleep(0.1)
            registerpage.refresh()
            ret = registerpage.register(self.user, self.password, True)
        assert isinstance(ret, LoginPage)
        return ret

    def login(self, loginpage):
        # TODO: test invalid user, incorrect password
        homepage = loginpage.login(self.user, self.password)
        # Should be logged in
        assert homepage.get_username() == self.user
        return homepage

    def create_post(self, homepage):
        newpostpage = homepage.newpost()
        self.post = Post(
            title="self.title selenium",
            body="self.body selenium",
            tags={"sele", "nium"},
        )
        # Try with missing title or body
        newpostpage.submit("", self.post.body, self.post.tags, False)
        newpostpage.submit(self.post.title, "", self.post.tags, False)
        newpostpage.submit(self.post.title, self.post.body, self.post.tags, False)
        assert "Invalid captcha" in newpostpage.errors
        return newpostpage.submit(self.post.title, self.post.body, self.post.tags, True)

    def check_post(self, post):
        assert post == self.post

    def edit_post(self, post):
        updatepage = post.edit()
        self.post = Post(
            title="edited title selenuim",
            body="edited body selenuim",
            tags={"selen", "ium"},
        )
        # Try with missing self.title or self.body
        updatepage.submit("", self.post.body, self.post.tags)
        updatepage.submit(self.post.title, "", self.post.tags)
        return updatepage.submit(self.post.title, self.post.body, self.post.tags)

    def create_comment(self, postpage):
        createpage = postpage.new_comment()
        # Missing body
        createpage.submit("")
        self.comment = Comment(body="Nice input!")
        # No captcha
        assert createpage.submit(self.comment.body) == createpage
        return createpage.submit(self.comment.body, recaptcha=True)

    def check_comment(self, comment):
        assert comment == self.comment

    def search(self, homepage):
        results = homepage.search("test3")
        (post,) = results.posts
        assert post.title == "test3"
        results = results.search("missing")
        assert not results.posts
        return results

    def browse_tags(self, homepage):
        tagspage = homepage.browse_tags()
        assert tagspage.tags == [
            Tag(name="tag1", count=2),
            Tag(name="tag2", count=2),
            Tag(name="ium", count=1),
            Tag(name="selen", count=1),
        ]
        tagpage = tagspage.tags[1].goto()
        assert tagpage.posts == [
            Post(title="test3", body="test3 word"),
            Post(title="test4", body="test4 word"),
        ]
        return tagpage

    def logout(self, homepage):
        homepage = homepage.logout()
        assert homepage.get_username() is None

    @pytest.mark.slow
    def test_tour(self, browser, live_server):
        self.browser = browser
        self.live_server = live_server
        loginpage = self.register()
        homepage = self.login(loginpage)
        postpage = self.create_post(homepage)
        post = postpage.post
        self.check_post(post)
        postpage = self.edit_post(post)
        post = postpage.post
        self.check_post(post)
        postpage = self.create_comment(postpage)
        (comment,) = postpage.comments
        self.check_comment(comment)
        results = self.search(postpage)
        tagpage = self.browse_tags(results)
        self.logout(tagpage)
