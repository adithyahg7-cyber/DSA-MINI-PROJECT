import hashlib
import secrets
import time

import config
import storage.db as db
from core.models import User
from core.search import index_user, rebuild_trie


def make_salt():
    return secrets.token_hex(16)


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100000).hex()


def _valid_username(name):
    if not isinstance(name, str):
        return False
    if not (config.USERNAME_MIN <= len(name) <= config.USERNAME_MAX):
        return False
    for char in name:
        if not (char == "_" or ("0" <= char <= "9") or ("a" <= char <= "z")):
            return False
    return True


def _rename_key(mapping, old, new):
    if old not in mapping:
        return
    value = mapping.pop(old)
    if new not in mapping:
        mapping[new] = value
        return
    target = mapping[new]
    if isinstance(target, set) and isinstance(value, set):
        target.update(value)
    elif isinstance(target, dict) and isinstance(value, dict):
        target.update(value)
    elif isinstance(target, list) and isinstance(value, list):
        target.extend(value)
    else:
        mapping[new] = value


def _replace_member(container, old, new):
    if isinstance(container, set):
        if old in container:
            container.discard(old)
            container.add(new)
    elif isinstance(container, dict):
        if old in container:
            container[new] = container.pop(old)
    elif isinstance(container, list):
        for index in range(len(container)):
            if container[index] == old:
                container[index] = new


def _replace_in_values(mapping, old, new):
    for value in mapping.values():
        _replace_member(value, old, new)


def signup(state, username, name, password, bio=""):
    username = username.strip().lower()
    name = name.strip()
    if not _valid_username(username):
        return False, "invalid username"
    if not name:
        return False, "name is required"
    if len(password) < config.PASSWORD_MIN:
        return False, "password must be at least " + str(config.PASSWORD_MIN) + " characters"
    if username in state.users:
        return False, "username already taken"
    salt = make_salt()
    user = User(
        username=username,
        name=name,
        salt=salt,
        password_hash=hash_password(password, salt),
        role="student",
        bio=bio,
        created_at=time.time(),
    )
    state.users[username] = user
    state.adj.setdefault(username, set())
    db.save_user(user)
    index_user(state, user)
    return True, "account created"


def login(state, username, password):
    username = username.strip().lower()
    user = state.users.get(username)
    if user is None:
        return False, "invalid username or password"
    if hash_password(password, user.salt) != user.password_hash:
        return False, "invalid username or password"
    state.current_user = username
    return True, "logged in"


def logout(state):
    state.current_user = None
    return True, "logged out"


def seed_admin(state):
    for user in state.users.values():
        if user.role == "admin":
            return
    username = config.ADMIN_USERNAME
    salt = make_salt()
    user = User(
        username=username,
        name=config.ADMIN_NAME,
        salt=salt,
        password_hash=hash_password(config.ADMIN_PASSWORD, salt),
        role="admin",
        bio="",
        created_at=time.time(),
    )
    state.users[username] = user
    state.adj.setdefault(username, set())
    db.save_user(user)
    index_user(state, user)


def set_role(state, actor_username, target_username, new_role):
    actor = state.users.get(actor_username)
    if actor is None or actor.role != "admin":
        return False, "permission denied"
    target = state.users.get(target_username)
    if target is None:
        return False, "user not found"
    if new_role not in config.ROLES:
        return False, "invalid role"
    if target.role == "admin" and new_role != "admin":
        admin_count = sum(1 for user in state.users.values() if user.role == "admin")
        if admin_count == 1:
            return False, "cannot demote the last admin"
    old_role = target.role
    target.role = new_role
    db.save_user(target)
    entry = {
        "id": state.next_id("role_log"),
        "actor": actor_username,
        "target": target_username,
        "old_role": old_role,
        "new_role": new_role,
        "created_at": time.time(),
    }
    state.role_log.append(entry)
    db.save_role_log(
        entry["id"],
        entry["actor"],
        entry["target"],
        entry["old_role"],
        entry["new_role"],
        entry["created_at"],
    )
    return True, "role updated"


def change_password(state, username, old_password, new_password):
    user = state.users.get(username)
    if user is None:
        return False, "user not found"
    if hash_password(old_password, user.salt) != user.password_hash:
        return False, "incorrect password"
    if len(new_password) < config.PASSWORD_MIN:
        return False, "password must be at least " + str(config.PASSWORD_MIN) + " characters"
    salt = make_salt()
    user.salt = salt
    user.password_hash = hash_password(new_password, salt)
    db.save_user(user)
    return True, "password updated"


def update_profile(state, username, name=None, bio=None):
    user = state.users.get(username)
    if user is None:
        return False, "user not found"
    name_changed = False
    if name is not None:
        cleaned_name = name.strip()
        if cleaned_name and cleaned_name != user.name:
            user.name = cleaned_name
            name_changed = True
    if bio is not None:
        cleaned_bio = bio.strip()
        if cleaned_bio:
            user.bio = cleaned_bio
    db.save_user(user)
    if name_changed:
        rebuild_trie(state)
    return True, "profile updated"


def update_avatar(state, username, avatar_path=None):
    user = state.users.get(username)
    if user is None:
        return False, "user not found"
    user.avatar = avatar_path or None
    db.save_user(user)
    return True, "profile photo updated"


def change_username(state, old, new):
    old = old.strip().lower()
    new = new.strip().lower()
    if old not in state.users:
        return False, "user not found"
    if old == new:
        return True, "username unchanged"
    if not _valid_username(new):
        return False, "invalid username"
    if new in state.users:
        return False, "username already taken"

    user = state.users.pop(old)
    user.username = new
    state.users[new] = user

    _rename_key(state.adj, old, new)
    _replace_in_values(state.adj, old, new)

    _rename_key(state.pending_out, old, new)
    _replace_in_values(state.pending_out, old, new)

    _rename_key(state.pending_in, old, new)
    _replace_in_values(state.pending_in, old, new)

    for post in state.posts.values():
        if post.author == old:
            post.author = new

    _rename_key(state.user_posts, old, new)

    _replace_in_values(state.likes, old, new)

    for bucket in state.comments.values():
        if isinstance(bucket, dict):
            for comment in bucket.values():
                if comment.author == old:
                    comment.author = new
        elif getattr(bucket, "author", None) == old:
            bucket.author = new

    _rename_key(state.notifications, old, new)
    _rename_key(state.unread, old, new)

    _rename_key(state.saved, old, new)

    _replace_in_values(state.rsvps, old, new)
    _rename_key(state.user_rsvps, old, new)

    _rename_key(state.user_communities, old, new)

    for community in state.communities.values():
        if community.owner == old:
            community.owner = new

    _replace_in_values(state.community_members, old, new)
    _replace_in_values(state.community_organisers, old, new)
    _replace_in_values(state.community_pending, old, new)

    for entry in state.role_log:
        if entry.get("actor") == old:
            entry["actor"] = new
        if entry.get("target") == old:
            entry["target"] = new

    for report in state.reports:
        if report.reporter == old:
            report.reporter = new
        if report.decided_by == old:
            report.decided_by = new

    updated_report_keys = set()
    for post_id, reporter in state.report_keys:
        updated_report_keys.add((post_id, new if reporter == old else reporter))
    state.report_keys.clear()
    state.report_keys.update(updated_report_keys)

    for event in state.events.values():
        if event.organiser == old:
            event.organiser = new

    for media_list in state.catalog.values():
        for media in media_list:
            if media.uploader == old:
                media.uploader = new

    for media_list in state.post_media.values():
        for media in media_list:
            if media.uploader == old:
                media.uploader = new

    for message in state.messages:
        if message.sender == old:
            message.sender = new
        if message.receiver == old:
            message.receiver = new

    for pitch in state.pitches:
        if pitch.proposer == old:
            pitch.proposer = new
        if pitch.decided_by == old:
            pitch.decided_by = new

    if state.current_user == old:
        state.current_user = new

    db.rename_user(old, new)
    rebuild_trie(state)
    return True, "username updated"


def is_admin(state, username):
    user = state.users.get(username)
    return bool(user is not None and user.role == "admin")
