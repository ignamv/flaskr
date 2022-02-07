from unittest.mock import MagicMock


def test_rss_link_in_index(client):
    expected = (
        '<link rel="alternate" type="application/rss+xml" title="RSS"'
        ' href="/feed.rss" />'
    )
    assert expected in client.get("/").data.decode()


def test_rss_feed_mocking_get_posts(client, monkeypatch):
    posts = [
        {"title": "tit1", "body": "o" * 200, "id": 1},
        {"title": "tit2", "body": "a" * 200, "id": 2},
    ]
    mock_get_posts = MagicMock(return_value=(2, posts))
    monkeypatch.setattr("flaskr.blog.rss.get_posts", mock_get_posts)
    response = client.get("/feed.rss").data.decode()
    mock_get_posts.assert_called_once_with(user_id=-1)
    assert (
        """<?xml version='1.0' encoding='UTF-8'?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" \
xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
  <channel>
    <title>Flaskr all comments feed</title>
    <link>http://localhost/</link>
    <description>A Flask learning experience</description>
    <docs>http://www.rssboard.org/rss-specification</docs>
    <generator>python-feedgen</generator>"""
        in response
    )
    assert (
        """<item>
      <title>tit2</title>
      <link>/2</link>
      <description>aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa</description>
    </item>
    <item>
      <title>tit1</title>
      <link>/1</link>
      <description>oooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooo</description>
    </item>
  </channel>
</rss>"""
        in response
    )
