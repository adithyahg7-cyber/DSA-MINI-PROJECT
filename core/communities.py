import time

import config
from core.models import Community
from core.posts import create_post
from storage import db


def _ensure(state, cid):
    state.community_members.setdefault(cid, set())
    state.community_organisers.setdefault(cid, set())
    state.community_pending.setdefault(cid, set())
    state.community_posts.setdefault(cid, [])


def _add_member(state, cid, username):
    _ensure(state, cid)
    state.community_members[cid].add(username)
    state.user_communities.setdefault(username, set()).add(cid)
    db.save_community_member(cid, username, "member")


def _add_organiser(state, cid, username):
    _ensure(state, cid)
    state.community_organisers[cid].add(username)
    state.community_members[cid].add(username)
    state.user_communities.setdefault(username, set()).add(cid)
    db.save_community_member(cid, username, "organiser")


def _add_pending(state, cid, username):
    _ensure(state, cid)
    state.community_pending[cid].add(username)
    db.save_community_member(cid, username, "pending")


def create_club(state, actor, name):
    user = state.users.get(actor)
    if user is None or user.role != "admin":
        return False, "Only admins can create clubs", None
    if not name or not name.strip():
        return False, "Name is required", None
    community_id = state.next_id("community")
    community = Community(
        community_id,
        name.strip(),
        "club",
        "public",
        actor,
        time.time(),
    )
    state.communities[community_id] = community
    db.save_community(community)
    _add_organiser(state, community_id, actor)
    return True, "Club created", community


def create_group(state, owner, name, visibility):
    if owner not in state.users:
        return False, "User not found", None
    if not name or not name.strip():
        return False, "Name is required", None
    if visibility not in config.VISIBILITIES:
        return False, "Invalid visibility", None
    community_id = state.next_id("community")
    community = Community(
        community_id,
        name.strip(),
        "group",
        visibility,
        owner,
        time.time(),
    )
    state.communities[community_id] = community
    db.save_community(community)
    _add_member(state, community_id, owner)
    return True, "Group created", community


def assign_organiser(state, actor, community_id, username):
    user = state.users.get(actor)
    if user is None or user.role != "admin":
        return False, "Only admins can assign organisers"
    community = state.communities.get(community_id)
    if community is None:
        return False, "Community not found"
    if community.kind != "club":
        return False, "Organisers can only be assigned to clubs"
    if username not in state.users:
        return False, "User not found"
    _ensure(state, community_id)
    if username in state.community_organisers[community_id]:
        return False, "User is already an organiser"
    _add_organiser(state, community_id, username)
    return True, "Organiser assigned"


def join_community(state, username, community_id):
    community = state.communities.get(community_id)
    if community is None:
        return False, "Community not found"
    if username not in state.users:
        return False, "User not found"
    _ensure(state, community_id)
    if username in state.community_members[community_id]:
        return False, "Already a member"
    if username in state.community_organisers[community_id]:
        return False, "Already a member"
    if username in state.community_pending[community_id]:
        return False, "Join request already pending"
    if community.kind == "club" or community.visibility == "public":
        _add_member(state, community_id, username)
        return True, "Joined community"
    _add_pending(state, community_id, username)
    return True, "Join request submitted"


def approve_join(state, actor, community_id, username):
    community = state.communities.get(community_id)
    if community is None:
        return False, "Community not found"
    _ensure(state, community_id)
    if actor != community.owner and actor not in state.community_organisers[community_id]:
        return False, "Only the owner or an organiser can approve requests"
    if username not in state.community_pending[community_id]:
        return False, "No pending request from this user"
    state.community_pending[community_id].discard(username)
    db.delete_community_member(community_id, username)
    _add_member(state, community_id, username)
    return True, "Join request approved"


def reject_join(state, actor, community_id, username):
    community = state.communities.get(community_id)
    if community is None:
        return False, "Community not found"
    _ensure(state, community_id)
    if actor != community.owner and actor not in state.community_organisers[community_id]:
        return False, "Only the owner or an organiser can reject requests"
    if username not in state.community_pending[community_id]:
        return False, "No pending request from this user"
    state.community_pending[community_id].discard(username)
    db.delete_community_member(community_id, username)
    return True, "Join request rejected"


def leave_community(state, username, community_id):
    community = state.communities.get(community_id)
    if community is None:
        return False, "Community not found"
    _ensure(state, community_id)
    if not is_member(state, username, community_id):
        return False, "You are not a member of this community"
    if username == community.owner:
        return False, "The owner cannot leave the community"
    state.community_members[community_id].discard(username)
    state.community_organisers[community_id].discard(username)
    user_communities = state.user_communities.get(username)
    if user_communities is not None:
        user_communities.discard(community_id)
    db.delete_community_member(community_id, username)
    return True, "Left community"


def is_member(state, username, community_id):
    if username in state.community_members.get(community_id, set()):
        return True
    return username in state.community_organisers.get(community_id, set())


def can_read(state, username, community_id):
    community = state.communities.get(community_id)
    if community is None:
        return False
    if community.kind == "club":
        return is_member(state, username, community_id)
    if community.visibility == "public":
        return True
    return is_member(state, username, community_id)


def can_post(state, username, community_id):
    if community_id not in state.communities:
        return False
    return is_member(state, username, community_id)


def community_members_list(state, community_id):
    _ensure(state, community_id)
    members = set(state.community_members[community_id])
    members.update(state.community_organisers[community_id])
    return sorted(members)


def community_pending_list(state, community_id):
    _ensure(state, community_id)
    return sorted(state.community_pending[community_id])


def community_feed(state, username, community_id, page=0):
    if community_id not in state.communities:
        return False, "Community not found", []
    if not can_read(state, username, community_id):
        return False, "You cannot read this community", []
    if page is None or page < 0:
        return True, "Feed loaded", []
    post_ids = state.community_posts.get(community_id, [])
    start = len(post_ids) - 1 - page * config.PAGE_SIZE
    if start < 0:
        return True, "Feed loaded", []
    posts = []
    for index in range(start, max(-1, start - config.PAGE_SIZE), -1):
        post = state.posts.get(post_ids[index])
        if post is not None:
            posts.append(post)
    return True, "Feed loaded", posts


def post_to_community(state, username, community_id, text, media_paths=None):
    if not can_post(state, username, community_id):
        return False, "You must be a member to post", None
    return create_post(state, username, text, community_id, media_paths)


def list_communities(state, username):
    entries = []
    for community in state.communities.values():
        cid = community.community_id
        entries.append(
            {
                "community": community,
                "joined": is_member(state, username, cid),
                "pending": username in state.community_pending.get(cid, set()),
            }
        )
    entries.sort(key=lambda entry: entry["community"].name)
    return entries
