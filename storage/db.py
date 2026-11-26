import os
import sqlite3
import threading

import config

_db_path = config.DB_PATH
_conn = None
_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    bio TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    avatar TEXT
);

CREATE TABLE IF NOT EXISTS connections (
    user_a TEXT NOT NULL,
    user_b TEXT NOT NULL,
    PRIMARY KEY (user_a, user_b)
);

CREATE TABLE IF NOT EXISTS pending (
    sender TEXT NOT NULL,
    receiver TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (sender, receiver)
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY,
    author TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at REAL NOT NULL,
    community_id INTEGER
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL,
    parent_id INTEGER,
    author TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS likes (
    post_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    PRIMARY KEY (post_id, username)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at REAL NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    venue TEXT NOT NULL,
    organiser TEXT NOT NULL,
    community_id INTEGER
);

CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    uploader TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS post_media (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    uploader TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    sender TEXT NOT NULL,
    receiver TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at REAL NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pitches (
    id INTEGER PRIMARY KEY,
    proposer TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    decided_by TEXT,
    decided_at REAL
);

CREATE TABLE IF NOT EXISTS communities (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    visibility TEXT NOT NULL,
    owner TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS community_members (
    community_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (community_id, username)
);

CREATE TABLE IF NOT EXISTS community_posts (
    community_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,
    PRIMARY KEY (community_id, post_id)
);

CREATE TABLE IF NOT EXISTS role_log (
    id INTEGER PRIMARY KEY,
    actor TEXT NOT NULL,
    target TEXT NOT NULL,
    old_role TEXT NOT NULL,
    new_role TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS rsvps (
    event_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    PRIMARY KEY (event_id, username)
);

CREATE TABLE IF NOT EXISTS saved_posts (
    username TEXT NOT NULL,
    post_id INTEGER NOT NULL,
    saved_at REAL NOT NULL,
    PRIMARY KEY (username, post_id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL,
    reporter TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    decided_by TEXT,
    decided_at REAL
);

CREATE TABLE IF NOT EXISTS uploads (
    path TEXT PRIMARY KEY,
    data BLOB NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream'
);
"""

TABLES = (
    "users",
    "connections",
    "pending",
    "posts",
    "comments",
    "likes",
    "notifications",
    "events",
    "media",
    "post_media",
    "messages",
    "pitches",
    "communities",
    "community_members",
    "community_posts",
    "role_log",
    "rsvps",
    "saved_posts",
    "reports",
    "uploads",
)


def set_db_path(path):
    global _db_path, _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _db_path = path
        _conn = None


def checkpoint():
    """Flush any pending journal data into the main database file."""
    with _lock:
        conn = get_conn()
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass


def refresh_connection():
    """Close the cached connection so a refreshed database file can be reloaded."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None


def get_conn():
    global _conn
    with _lock:
        if _conn is None:
            directory = os.path.dirname(_db_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            # Vercel creates the connection during cold start but serves the
            # request from a different thread, so allow cross-thread use and
            # serialize access with _lock.
            _conn = sqlite3.connect(_db_path, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
        return _conn


def execute(sql, params=()):
    with _lock:
        conn = get_conn()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor


def query(sql, params=()):
    with _lock:
        return [dict(row) for row in get_conn().execute(sql, params).fetchall()]


def init_db():
    with _lock:
        conn = get_conn()
        conn.executescript(SCHEMA)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "avatar" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN avatar TEXT")
        conn.commit()


def clear_all():
    for table in TABLES:
        execute("DELETE FROM " + table)


def save_user(user):
    execute(
        "INSERT OR REPLACE INTO users (username, name, salt, password_hash, role, bio, created_at, avatar) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user.username, user.name, user.salt, user.password_hash, user.role, user.bio, user.created_at, getattr(user, "avatar", None)),
    )


def save_connection(user_a, user_b):
    execute("INSERT OR IGNORE INTO connections (user_a, user_b) VALUES (?, ?)", (user_a, user_b))


def delete_connection(user_a, user_b):
    execute("DELETE FROM connections WHERE user_a = ? AND user_b = ?", (user_a, user_b))


def save_pending(sender, receiver, created_at):
    execute(
        "INSERT OR REPLACE INTO pending (sender, receiver, created_at) VALUES (?, ?, ?)",
        (sender, receiver, created_at),
    )


def delete_pending(sender, receiver):
    execute("DELETE FROM pending WHERE sender = ? AND receiver = ?", (sender, receiver))


def save_post(post):
    execute(
        "INSERT OR REPLACE INTO posts (id, author, text, created_at, community_id) VALUES (?, ?, ?, ?, ?)",
        (post.post_id, post.author, post.text, post.created_at, post.community_id),
    )


def delete_post_row(post_id):
    execute("DELETE FROM posts WHERE id = ?", (post_id,))


def save_comment(comment):
    execute(
        "INSERT OR REPLACE INTO comments (id, post_id, parent_id, author, text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (comment.comment_id, comment.post_id, comment.parent_id, comment.author, comment.text, comment.created_at),
    )


def delete_comment(comment_id):
    execute("DELETE FROM comments WHERE id = ?", (comment_id,))


def delete_comments_for_post(post_id):
    execute("DELETE FROM comments WHERE post_id = ?", (post_id,))


def save_like(post_id, username):
    execute("INSERT OR IGNORE INTO likes (post_id, username) VALUES (?, ?)", (post_id, username))


def delete_likes_for_post(post_id):
    execute("DELETE FROM likes WHERE post_id = ?", (post_id,))


def delete_like(post_id, username):
    execute("DELETE FROM likes WHERE post_id = ? AND username = ?", (post_id, username))


def save_notification(note):
    execute(
        "INSERT OR REPLACE INTO notifications (id, username, text, created_at, is_read) VALUES (?, ?, ?, ?, ?)",
        (note.notification_id, note.username, note.text, note.created_at, int(note.is_read)),
    )


def mark_notification_read(note_id):
    execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (note_id,))


def save_event(event):
    execute(
        "INSERT OR REPLACE INTO events (id, title, description, date, time, venue, organiser, community_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (event.event_id, event.title, event.description, event.date, event.time, event.venue, event.organiser, event.community_id),
    )


def save_media(media):
    execute(
        "INSERT OR REPLACE INTO media (id, event_id, path, uploader, created_at) VALUES (?, ?, ?, ?, ?)",
        (media.media_id, media.event_id, media.path, media.uploader, media.created_at),
    )


def save_post_media(media):
    execute(
        "INSERT OR REPLACE INTO post_media (id, post_id, path, uploader, created_at) VALUES (?, ?, ?, ?, ?)",
        (media.media_id, media.post_id, media.path, media.uploader, media.created_at),
    )


def delete_post_media_for_post(post_id):
    execute("DELETE FROM post_media WHERE post_id = ?", (post_id,))


def save_message(message):
    execute(
        "INSERT OR REPLACE INTO messages (id, sender, receiver, text, created_at, is_read) VALUES (?, ?, ?, ?, ?, ?)",
        (message.message_id, message.sender, message.receiver, message.text, message.created_at, int(message.is_read)),
    )


def mark_message_read(message_id):
    execute("UPDATE messages SET is_read = 1 WHERE id = ?", (message_id,))


def save_pitch(pitch):
    execute(
        "INSERT OR REPLACE INTO pitches (id, proposer, title, description, status, created_at, decided_by, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pitch.pitch_id, pitch.proposer, pitch.title, pitch.description, pitch.status, pitch.created_at, pitch.decided_by, pitch.decided_at),
    )


def save_community(community):
    execute(
        "INSERT OR REPLACE INTO communities (id, name, kind, visibility, owner, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (community.community_id, community.name, community.kind, community.visibility, community.owner, community.created_at),
    )


def save_community_member(community_id, username, role):
    execute(
        "INSERT OR REPLACE INTO community_members (community_id, username, role) VALUES (?, ?, ?)",
        (community_id, username, role),
    )


def delete_community_member(community_id, username):
    execute("DELETE FROM community_members WHERE community_id = ? AND username = ?", (community_id, username))


def save_community_post(community_id, post_id):
    execute("INSERT OR IGNORE INTO community_posts (community_id, post_id) VALUES (?, ?)", (community_id, post_id))


def delete_community_post(community_id, post_id):
    execute("DELETE FROM community_posts WHERE community_id = ? AND post_id = ?", (community_id, post_id))


def save_role_log(entry_id, actor, target, old_role, new_role, created_at):
    execute(
        "INSERT OR REPLACE INTO role_log (id, actor, target, old_role, new_role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (entry_id, actor, target, old_role, new_role, created_at),
    )


def save_rsvp(event_id, username):
    execute("INSERT OR IGNORE INTO rsvps (event_id, username) VALUES (?, ?)", (event_id, username))


def delete_rsvp(event_id, username):
    execute("DELETE FROM rsvps WHERE event_id = ? AND username = ?", (event_id, username))


def save_saved_post(username, post_id, saved_at):
    execute(
        "INSERT OR REPLACE INTO saved_posts (username, post_id, saved_at) VALUES (?, ?, ?)",
        (username, post_id, saved_at),
    )


def delete_saved_post(username, post_id):
    execute("DELETE FROM saved_posts WHERE username = ? AND post_id = ?", (username, post_id))


def delete_saved_for_post(post_id):
    execute("DELETE FROM saved_posts WHERE post_id = ?", (post_id,))


def save_report(report):
    execute(
        "INSERT OR REPLACE INTO reports (id, post_id, reporter, reason, status, created_at, decided_by, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (report.report_id, report.post_id, report.reporter, report.reason, report.status, report.created_at, report.decided_by, report.decided_at),
    )


def delete_reports_for_post(post_id):
    execute("DELETE FROM reports WHERE post_id = ?", (post_id,))


def rename_user(old, new):
    with _lock:
        conn = get_conn()
        statements = (
            ("UPDATE users SET username = ? WHERE username = ?", (new, old)),
            ("UPDATE connections SET user_a = ? WHERE user_a = ?", (new, old)),
            ("UPDATE connections SET user_b = ? WHERE user_b = ?", (new, old)),
            ("UPDATE pending SET sender = ? WHERE sender = ?", (new, old)),
            ("UPDATE pending SET receiver = ? WHERE receiver = ?", (new, old)),
            ("UPDATE posts SET author = ? WHERE author = ?", (new, old)),
            ("UPDATE comments SET author = ? WHERE author = ?", (new, old)),
            ("UPDATE likes SET username = ? WHERE username = ?", (new, old)),
            ("UPDATE post_media SET uploader = ? WHERE uploader = ?", (new, old)),
            ("UPDATE messages SET sender = ? WHERE sender = ?", (new, old)),
            ("UPDATE messages SET receiver = ? WHERE receiver = ?", (new, old)),
            ("UPDATE notifications SET username = ? WHERE username = ?", (new, old)),
            ("UPDATE events SET organiser = ? WHERE organiser = ?", (new, old)),
            ("UPDATE media SET uploader = ? WHERE uploader = ?", (new, old)),
            ("UPDATE pitches SET proposer = ? WHERE proposer = ?", (new, old)),
            ("UPDATE communities SET owner = ? WHERE owner = ?", (new, old)),
            ("UPDATE community_members SET username = ? WHERE username = ?", (new, old)),
            ("UPDATE role_log SET actor = ? WHERE actor = ?", (new, old)),
            ("UPDATE role_log SET target = ? WHERE target = ?", (new, old)),
            ("UPDATE rsvps SET username = ? WHERE username = ?", (new, old)),
            ("UPDATE saved_posts SET username = ? WHERE username = ?", (new, old)),
            ("UPDATE reports SET reporter = ? WHERE reporter = ?", (new, old)),
            ("UPDATE reports SET decided_by = ? WHERE decided_by = ?", (new, old)),
        )
        for sql, params in statements:
            conn.execute(sql, params)
        conn.commit()


def save_blob(path, data, content_type):
    execute(
        "INSERT OR REPLACE INTO uploads (path, data, content_type) VALUES (?, ?, ?)",
        (path, data, content_type or "application/octet-stream"),
    )


def get_blob(path):
    rows = query("SELECT data, content_type FROM uploads WHERE path = ?", (path,))
    return rows[0] if rows else None
