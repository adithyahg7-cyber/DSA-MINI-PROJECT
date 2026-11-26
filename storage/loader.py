import heapq
from collections import deque

from core.models import (
    Community,
    Comment,
    Event,
    Media,
    Message,
    Notification,
    PostMedia,
    Pitch,
    Post,
    Report,
    User,
)
from core.search import rebuild_trie
from storage import db


def _max_counter(rows, key):
    if not rows:
        return 1
    return max(row[key] for row in rows) + 1


def load(state):
    state.reset()

    for row in db.query("SELECT * FROM users ORDER BY created_at"):
        user = User(
            username=row["username"],
            name=row["name"],
            salt=row["salt"],
            password_hash=row["password_hash"],
            role=row["role"],
            bio=row["bio"],
            created_at=row["created_at"],
            avatar=row.get("avatar"),
        )
        state.users[user.username] = user
        state.adj.setdefault(user.username, set())

    for row in db.query("SELECT * FROM connections"):
        state.adj.setdefault(row["user_a"], set()).add(row["user_b"])
        state.adj.setdefault(row["user_b"], set()).add(row["user_a"])

    for row in db.query("SELECT * FROM pending ORDER BY created_at"):
        state.pending_out.setdefault(row["sender"], {})[row["receiver"]] = row["created_at"]
        state.pending_in.setdefault(row["receiver"], {})[row["sender"]] = row["created_at"]

    post_rows = db.query("SELECT * FROM posts ORDER BY created_at, id")
    for row in post_rows:
        post = Post(
            post_id=row["id"],
            author=row["author"],
            text=row["text"],
            created_at=row["created_at"],
            community_id=row["community_id"],
        )
        state.posts[post.post_id] = post
        state.user_posts.setdefault(post.author, []).append(post.post_id)
        state.all_posts.append(post.post_id)

    post_media_rows = db.query("SELECT * FROM post_media ORDER BY id")
    for row in post_media_rows:
        media = PostMedia(
            media_id=row["id"],
            post_id=row["post_id"],
            path=row["path"],
            uploader=row["uploader"],
            created_at=row["created_at"],
        )
        state.post_media.setdefault(media.post_id, []).append(media)
        post = state.posts.get(media.post_id)
        if post is not None:
            post.media.append(media)

    for row in db.query("SELECT * FROM comments ORDER BY created_at, id"):
        comment = Comment(
            comment_id=row["id"],
            post_id=row["post_id"],
            author=row["author"],
            text=row["text"],
            created_at=row["created_at"],
            parent_id=row["parent_id"],
        )
        state.comments.setdefault(comment.post_id, {})[comment.comment_id] = comment

    for row in db.query("SELECT * FROM likes"):
        state.likes.setdefault(row["post_id"], set()).add(row["username"])

    notification_rows = db.query("SELECT * FROM notifications ORDER BY id")
    for row in notification_rows:
        note = Notification(
            notification_id=row["id"],
            username=row["username"],
            text=row["text"],
            created_at=row["created_at"],
            is_read=bool(row["is_read"]),
        )
        state.notifications.setdefault(note.username, deque()).append(note)
        if not note.is_read:
            state.unread[note.username] = state.unread.get(note.username, 0) + 1

    message_rows = db.query("SELECT * FROM messages ORDER BY created_at, id")
    for row in message_rows:
        state.messages.append(
            Message(
                message_id=row["id"],
                sender=row["sender"],
                receiver=row["receiver"],
                text=row["text"],
                created_at=row["created_at"],
                is_read=bool(row["is_read"]),
            )
        )

    event_rows = db.query("SELECT * FROM events ORDER BY date, id")
    for row in event_rows:
        event = Event(
            event_id=row["id"],
            title=row["title"],
            description=row["description"],
            date=row["date"],
            time=row["time"],
            venue=row["venue"],
            organiser=row["organiser"],
            community_id=row["community_id"],
        )
        state.events[event.event_id] = event
        state.events_by_date.setdefault(event.date, []).append(event.event_id)
        heapq.heappush(state.event_heap, (event.date, event.event_id))

    for row in db.query("SELECT * FROM media ORDER BY id"):
        media = Media(
            media_id=row["id"],
            event_id=row["event_id"],
            path=row["path"],
            uploader=row["uploader"],
            created_at=row["created_at"],
        )
        state.catalog.setdefault(media.event_id, []).append(media)

    pitch_rows = db.query("SELECT * FROM pitches ORDER BY id")
    for row in pitch_rows:
        pitch = Pitch(
            pitch_id=row["id"],
            proposer=row["proposer"],
            title=row["title"],
            description=row["description"],
            status=row["status"],
            created_at=row["created_at"],
            decided_by=row["decided_by"],
            decided_at=row["decided_at"],
        )
        state.pitches.append(pitch)

    for row in db.query("SELECT * FROM communities ORDER BY name"):
        community = Community(
            community_id=row["id"],
            name=row["name"],
            kind=row["kind"],
            visibility=row["visibility"],
            owner=row["owner"],
            created_at=row["created_at"],
        )
        state.communities[community.community_id] = community
        state.community_members.setdefault(community.community_id, set())
        state.community_organisers.setdefault(community.community_id, set())
        state.community_pending.setdefault(community.community_id, set())
        state.community_posts.setdefault(community.community_id, [])

    for row in db.query("SELECT * FROM community_members"):
        cid = row["community_id"]
        username = row["username"]
        role = row["role"]
        if role == "pending":
            state.community_pending.setdefault(cid, set()).add(username)
            continue
        state.community_members.setdefault(cid, set()).add(username)
        state.user_communities.setdefault(username, set()).add(cid)
        if role == "organiser":
            state.community_organisers.setdefault(cid, set()).add(username)

    for row in db.query("SELECT * FROM community_posts ORDER BY post_id"):
        state.community_posts.setdefault(row["community_id"], []).append(row["post_id"])

    for row in db.query("SELECT * FROM role_log ORDER BY id"):
        state.role_log.append(
            {
                "id": row["id"],
                "actor": row["actor"],
                "target": row["target"],
                "old_role": row["old_role"],
                "new_role": row["new_role"],
                "created_at": row["created_at"],
            }
        )

    for row in db.query("SELECT * FROM rsvps"):
        state.rsvps.setdefault(row["event_id"], set()).add(row["username"])
        state.user_rsvps.setdefault(row["username"], set()).add(row["event_id"])

    for row in db.query("SELECT * FROM saved_posts ORDER BY saved_at"):
        state.saved.setdefault(row["username"], {})[row["post_id"]] = row["saved_at"]

    report_rows = db.query("SELECT * FROM reports ORDER BY id")
    for row in report_rows:
        report = Report(
            report_id=row["id"],
            post_id=row["post_id"],
            reporter=row["reporter"],
            reason=row["reason"],
            status=row["status"],
            created_at=row["created_at"],
            decided_by=row["decided_by"],
            decided_at=row["decided_at"],
        )
        state.reports.append(report)
        state.report_keys.add((report.post_id, report.reporter))

    state.counters["post"] = _max_counter(post_rows, "id")
    state.counters["comment"] = _max_counter(db.query("SELECT id FROM comments"), "id")
    state.counters["notification"] = _max_counter(notification_rows, "id")
    state.counters["event"] = _max_counter(event_rows, "id")
    state.counters["media"] = _max_counter(db.query("SELECT id FROM media"), "id")
    state.counters["post_media"] = _max_counter(post_media_rows, "id")
    state.counters["message"] = _max_counter(message_rows, "id")
    state.counters["pitch"] = _max_counter(pitch_rows, "id")
    state.counters["community"] = _max_counter(db.query("SELECT id FROM communities"), "id")
    state.counters["report"] = _max_counter(report_rows, "id")
    state.counters["role_log"] = _max_counter(db.query("SELECT id FROM role_log"), "id")

    state.current_user = None
    rebuild_trie(state)
