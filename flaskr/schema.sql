DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS post;

CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

CREATE TABLE post (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    imagebytes BLOB,
    FOREIGN KEY (author_id) REFERENCES user (id)
);

-- For posts index (sorted by date)
CREATE INDEX post__created ON post (created);

-- For posts index, just need author name and checking if the post has an image
CREATE VIEW posts_view AS
    SELECT post.id AS id, title, body, created, author_id, username,
    imagebytes NOTNULL AS has_image
    FROM post
    JOIN user author ON post.author_id == author.id;

CREATE TABLE like (
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (post_id) REFERENCES post (id)
    FOREIGN KEY (user_id) REFERENCES user (id)
    PRIMARY KEY (post_id, user_id)
);

CREATE TABLE comment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    body TEXT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES post (id)
    FOREIGN KEY (author_id) REFERENCES user (id)
);

-- For post comments view (sorted by date)
CREATE INDEX comment__created ON comment (created);

CREATE TABLE tag (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
    CHECK (name <> "")
);

CREATE INDEX tag__name ON tag (name);

CREATE TABLE post_tag (
    post_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    FOREIGN KEY (post_id) REFERENCES post (id)
    FOREIGN KEY (tag_id) REFERENCES tag (id)
    PRIMARY KEY (post_id, tag_id)
);

CREATE INDEX post_tag__tag_id ON post_tag (tag_id);

