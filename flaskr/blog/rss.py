from flask import request, url_for
from .blueprint import bp
from feedgen.feed import FeedGenerator
from .blogdb import get_posts


@bp.route("/feed.rss")
def rss_feed():
    rss_feed_description_chars = 100
    generator = FeedGenerator()
    generator.title("Flaskr all comments feed")
    generator.link(href=request.url_root)
    generator.description("A Flask learning experience")
    for post in get_posts(user_id=-1):
        entry = generator.add_entry()
        entry.title(post["title"])
        entry.link(href=url_for("blog.post", post_id=post["id"]))
        entry.description(post["body"][:rss_feed_description_chars])
    return generator.rss_str(pretty=True)
