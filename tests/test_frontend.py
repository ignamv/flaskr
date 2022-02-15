import re
import pytest
import attr
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
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
        WebDriverWait(webdriver, timeout=2).until(self.in_correct_page)
        self.webdriver = webdriver

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
        body = element.find_element(By.CLASS_NAME, "body").text
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
        self.element.find_element(By.ID, "edit").click()
        return UpdatePostPage(self.webdriver)


class PostPage(PageObject):
    def in_correct_page(self, webdriver):
        # Post page should have exactly one post
        return len(webdriver.find_elements(By.CLASS_NAME, "post_title")) == 1

    @property
    def post(self):
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
        self.post = Post(
            title="self.title selenium",
            body="self.body selenium",
            tags={"sele", "nium"},
        )
        # Try with missing title or body
        newpostpage.submit_bad("", self.post.body, self.post.tags)
        newpostpage.submit_bad(self.post.title, "", self.post.tags)
        return newpostpage.submit_good(self.post.title, self.post.body, self.post.tags)

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
        updatepage.submit_bad("", self.post.body, self.post.tags)
        updatepage.submit_bad(self.post.title, "", self.post.tags)
        return updatepage.submit_good(self.post.title, self.post.body, self.post.tags)

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
            Tag("tag1", 2),
            Tag("tag2", 2),
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

    def test_tour(self, browser):
        self.browser = browser
        loginpage = self.register()
        homepage = self.login(loginpage)
        postpage = self.create_post(homepage)
        post = postpage.post
        self.check_post(post)
        postpage = self.edit_post(post)
        post = postpage.post
        self.check_post(post)
        homepage = postpage.go_home()
        results = self.search(homepage)
        tagpage = self.browse_tags(results)
        self.logout(tagpage)
