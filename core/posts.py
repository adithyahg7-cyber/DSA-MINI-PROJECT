import heapq
import time

import config
from core.models import Comment, Post, PostMedia, Report
from storage import db


def _now():
    return time.time()


def _remove_from(values, item):
    try:
        values.remove(item)
    except (ValueError, AttributeError):
        pass


def create_post(state, author, text, community_id=None, media_paths=None):
    if author not in state.users:
        return False, "User not found.", None
    text = text.strip() if isinstance(text, str) else ""
    paths = []
    for path in media_paths or []:
        if isinstance(path, str) and path.strip():
            paths.append(path.strip())
    if not text and not paths:
        return False, "Post text or media is required.", None
    post_id = state.next_id("post")
    post = Post(post_id, author, text, _now(), community_id)
    state.posts[post_id] = post
    state.user_posts.setdefault(author, []).append(post_id)
    state.all_posts.append(post_id)
    db.save_post(post)
    for path in paths:
        media = PostMedia(state.next_id("post_media"), post_id, path, author, post.created_at)
        state.post_media.setdefault(post_id, []).append(media)
        post.media.append(media)
        db.save_post_media(media)
    if community_id is not None:
        state.community_posts.setdefault(community_id, []).append(post_id)
        db.save_community_post(community_id, post_id)
    return True, "Post created.", post


def delete_post(state, actor, post_id):
    post = state.posts.get(post_id)
    if post is None:
        return False, "Post not found."
    actor_user = state.users.get(actor)
    if actor != post.author and (actor_user is None or actor_user.role != "admin"):
        return False, "Not allowed to delete this post."
    del state.posts[post_id]
    if post.author in state.user_posts:
        _remove_from(state.user_posts[post.author], post_id)
    _remove_from(state.all_posts, post_id)
    if post.community_id is not None and post.community_id in state.community_posts:
        _remove_from(state.community_posts[post.community_id], post_id)
    state.comments.pop(post_id, None)
    state.likes.pop(post_id, None)
    state.post_media.pop(post_id, None)
    for username in list(state.saved):
        bucket = state.saved.get(username)
        if bucket is not None and post_id in bucket:
            del bucket[post_id]
    db.delete_post_row(post_id)
    db.delete_comments_for_post(post_id)
    db.delete_likes_for_post(post_id)
    db.delete_post_media_for_post(post_id)
    db.delete_saved_for_post(post_id)
    if post.community_id is not None:
        db.delete_community_post(post.community_id, post_id)
    return True, "Post deleted."


def own_posts(state, username):
    ids = state.user_posts.get(username, [])
    posts = [state.posts[pid] for pid in ids if pid in state.posts]
    posts.sort(key=lambda post: (post.created_at, post.post_id), reverse=True)
    return posts


def explore_feed(state, page=0):
    if page is None or page < 0:
        page = 0
    ordered = list(reversed(state.all_posts))
    start = page * config.PAGE_SIZE
    window = ordered[start:start + config.PAGE_SIZE]
    return [state.posts[pid] for pid in window if pid in state.posts]


def connections_feed(state, username, page=0):
    if page is None or page < 0:
        page = 0
    needed = (page + 1) * config.PAGE_SIZE
    connections = list(state.adj.get(username, []))
    heap = []
    for index, other in enumerate(connections):
        ids = state.user_posts.get(other, [])
        position = len(ids) - 1
        while position >= 0 and ids[position] not in state.posts:
            position -= 1
        if position >= 0:
            post = state.posts[ids[position]]
            heapq.heappush(heap, (-post.created_at, -post.post_id, post.post_id, index, position))
    collected = []
    while heap and len(collected) < needed:
        _, _, post_id, index, position = heapq.heappop(heap)
        collected.append(state.posts[post_id])
        position -= 1
        ids = state.user_posts.get(connections[index], [])
        while position >= 0 and ids[position] not in state.posts:
            position -= 1
        if position >= 0:
            post = state.posts[ids[position]]
            heapq.heappush(heap, (-post.created_at, -post.post_id, post.post_id, index, position))
    start = page * config.PAGE_SIZE
    return collected[start:start + config.PAGE_SIZE]


def like_post(state, username, post_id):
    if post_id not in state.posts:
        return False, "Post not found."
    if username not in state.users:
        return False, "User not found."
    bucket = state.likes.setdefault(post_id, set())
    if username in bucket:
        return False, "Post already liked."
    bucket.add(username)
    db.save_like(post_id, username)
    return True, "Post liked."


def unlike_post(state, username, post_id):
    if post_id not in state.posts:
        return False, "Post not found."
    bucket = state.likes.get(post_id)
    if bucket is None or username not in bucket:
        return False, "Post not liked."
    bucket.discard(username)
    db.delete_like(post_id, username)
    return True, "Like removed."


def likes_for(state, post_id):
    return set(state.likes.get(post_id, set()))


def like_count(state, post_id):
    return len(state.likes.get(post_id, set()))


def add_comment(state, author, post_id, text, parent_id=None):
    if post_id not in state.posts:
        return False, "Post not found.", None
    if not isinstance(text, str) or not text.strip():
        return False, "Comment text is required.", None
    text = text.strip()
    bucket = state.comments.get(post_id, {})
    if parent_id is not None and parent_id not in bucket:
        return False, "Parent comment not found.", None
    comment_id = state.next_id("comment")
    comment = Comment(comment_id, post_id, author, text, _now(), parent_id)
    state.comments.setdefault(post_id, {})[comment_id] = comment
    db.save_comment(comment)
    return True, "Comment added.", comment


def comment_tree(state, post_id):
    bucket = state.comments.get(post_id, {})
    ordered = sorted(bucket.values(), key=lambda comment: (comment.created_at, comment.comment_id))
    children = {}
    roots = []
    for comment in ordered:
        if comment.parent_id is None or comment.parent_id not in bucket:
            roots.append(comment)
        else:
            children.setdefault(comment.parent_id, []).append(comment)

    def build(comment):
        replies = [build(child) for child in children.get(comment.comment_id, [])]
        return {"comment": comment, "replies": replies}

    return [build(root) for root in roots]


def comment_count(state, post_id):
    return len(state.comments.get(post_id, {}))


def delete_comment(state, actor, post_id, comment_id):
    post = state.posts.get(post_id)
    if post is None:
        return False, "Post not found."
    bucket = state.comments.get(post_id)
    if bucket is None or comment_id not in bucket:
        return False, "Comment not found."
    actor_user = state.users.get(actor)
    target = bucket[comment_id]
    allowed = actor == target.author or actor == post.author
    if not allowed and actor_user is not None and actor_user.role == "admin":
        allowed = True
    if not allowed:
        return False, "You cannot delete this comment."
    to_delete = {comment_id}
    changed = True
    while changed:
        changed = False
        for comment_id_value, comment in bucket.items():
            if comment.parent_id in to_delete and comment_id_value not in to_delete:
                to_delete.add(comment_id_value)
                changed = True
    for value in to_delete:
        bucket.pop(value, None)
        db.delete_comment(value)
    return True, "Comment deleted."


def trending_posts(state, username, limit=10):
    if limit is None or limit <= 0:
        return []
    connections = set(state.adj.get(username, []))
    if not connections:
        return []
    now = _now()
    horizon = config.TRENDING_DAYS * 86400.0
    candidates = []
    for other in connections:
        for post_id in state.user_posts.get(other, []):
            post = state.posts.get(post_id)
            if post is None:
                continue
            age_seconds = now - post.created_at
            if age_seconds < 0:
                age_seconds = 0.0
            if age_seconds > horizon:
                continue
            score = (len(state.likes.get(post_id, ())) + 2 * comment_count(state, post_id)) / (age_seconds / 86400.0 + 1.0)
            candidates.append((post, score))
    top = heapq.nlargest(limit, candidates, key=lambda entry: entry[1])
    return [(post, round(score, 3)) for post, score in top]


def save_post(state, username, post_id):
    if post_id not in state.posts:
        return False, "Post not found."
    state.saved.setdefault(username, {})[post_id] = _now()
    db.save_saved_post(username, post_id, state.saved[username][post_id])
    return True, "Post saved."


def unsave_post(state, username, post_id):
    bucket = state.saved.get(username)
    if bucket is None or post_id not in bucket:
        return False, "Post not saved."
    del bucket[post_id]
    db.delete_saved_post(username, post_id)
    return True, "Post unsaved."


def saved_posts(state, username):
    bucket = state.saved.get(username, {})
    entries = sorted(bucket.items(), key=lambda item: (item[1], item[0]), reverse=True)
    result = []
    for post_id, _ in entries:
        post = state.posts.get(post_id)
        if post is None:
            bucket.pop(post_id, None)
            db.delete_saved_post(username, post_id)
            continue
        result.append(post)
    return result


def report_post(state, reporter, post_id, reason):
    post = state.posts.get(post_id)
    if post is None:
        return False, "Post not found.", None
    if reporter == post.author:
        return False, "You cannot report your own post.", None
    key = (post_id, reporter)
    if key in state.report_keys:
        return False, "Post already reported.", None
    if not isinstance(reason, str) or not reason.strip():
        return False, "Report reason is required.", None
    reason = reason.strip()
    report_id = state.next_id("report")
    report = Report(report_id, post_id, reporter, reason, "pending", _now())
    state.reports.append(report)
    state.report_keys.add(key)
    db.save_report(report)
    return True, "Report submitted.", report


def moderation_queue(state, actor):
    user = state.users.get(actor)
    if user is None or user.role != "admin":
        return False, "Admin access required.", []
    pending = [report for report in state.reports if report.status == "pending"]
    pending.sort(key=lambda report: (report.created_at, report.report_id))
    return True, "Pending reports.", pending


def review_report(state, actor, report_id, action):
    user = state.users.get(actor)
    if user is None or user.role != "admin":
        return False, "Admin access required."
    if action not in ("dismiss", "remove"):
        return False, "Invalid action."
    report = None
    for entry in state.reports:
        if entry.report_id == report_id:
            report = entry
            break
    if report is None:
        return False, "Report not found."
    if report.status != "pending":
        return False, "Report already reviewed."
    report.status = "dismissed" if action == "dismiss" else "actioned"
    report.decided_by = actor
    report.decided_at = _now()
    db.save_report(report)
    if action == "remove":
        delete_post(state, actor, report.post_id)
    return True, "Report reviewed."
