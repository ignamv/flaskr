# Flask-based blog webapp

This is a blog webapp I developed using Flask and SQLite.
I followed a TDD approach,
starting from the [Flaskr tutorial](https://flask.palletsprojects.com/en/2.0.x/tutorial/)
and going on to implement the following features:

* New responsive HTML+CSS layout and style from scratch
* Paging
* Uploading images with posts
* Search function
* "Liking" posts
* Commenting on posts
* Tagging posts
* RSS feed
* Database indexes to speed up common queries
* Database views to eliminate repeated SQL queries

Pending features:

* Page showing all tags with counts
* Spam prevention
    - Captchas for account registration, posting, commenting
    - rel=nofollow
    - Rate limiting
* OAuth
* Password reminders
