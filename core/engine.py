import config
from core import auth, communities, events, graph, messages, notifications, posts, search
from core.state import State
from storage import db, loader


class Engine:
    def __init__(self, db_path=None):
        if db_path is not None:
            db.set_db_path(db_path)
        db.init_db()
        self.state = State()
        loader.load(self.state)
        auth.seed_admin(self.state)

    @property
    def me(self):
        return self.state.current_user

    def reload(self):
        loader.load(self.state)

    def _need(self):
        return self.state.current_user

    def _denied(self):
        return (False, "log in first")

    def signup(self, username, name, password, bio=""):
        return auth.signup(self.state, username, name, password, bio)

    def login(self, username, password):
        return auth.login(self.state, username, password)

    def logout(self):
        return auth.logout(self.state)

    def seed_admin(self):
        auth.seed_admin(self.state)

    def set_role(self, target, new_role):
        user = self._need()
        if user is None:
            return self._denied()
        ok, msg = auth.set_role(self.state, user, target, new_role)
        if ok:
            notifications.push(self.state, target, f"Your role was changed to {new_role} by {user}")
        return ok, msg

    def role_log(self):
        return list(self.state.role_log)

    def change_password(self, old_password, new_password):
        user = self._need()
        if user is None:
            return self._denied()
        return auth.change_password(self.state, user, old_password, new_password)

    def update_profile(self, name=None, bio=None):
        user = self._need()
        if user is None:
            return self._denied()
        return auth.update_profile(self.state, user, name, bio)

    def update_avatar(self, avatar_path):
        user = self._need()
        if user is None:
            return self._denied()
        return auth.update_avatar(self.state, user, avatar_path)

    def change_username(self, new_username):
        user = self._need()
        if user is None:
            return self._denied()
        ok, msg = auth.change_username(self.state, user, new_username)
        if ok:
            self.state.current_user = new_username.strip().lower()
        return ok, msg

    def search_users(self, prefix, limit=config.SEARCH_LIMIT):
        return search.search_users(self.state, prefix, limit)

    def send_request(self, receiver):
        user = self._need()
        if user is None:
            return self._denied()
        ok, msg = graph.send_request(self.state, user, receiver)
        if ok:
            notifications.push(self.state, receiver, f"{user} sent you a connection request")
        return ok, msg

    def accept_request(self, sender):
        user = self._need()
        if user is None:
            return self._denied()
        ok, msg = graph.accept_request(self.state, user, sender)
        if ok:
            notifications.push(self.state, sender, f"{user} accepted your connection request")
        return ok, msg

    def reject_request(self, sender):
        user = self._need()
        if user is None:
            return self._denied()
        return graph.reject_request(self.state, user, sender)

    def cancel_request(self, receiver):
        user = self._need()
        if user is None:
            return self._denied()
        return graph.cancel_request(self.state, user, receiver)

    def remove_connection(self, other):
        user = self._need()
        if user is None:
            return self._denied()
        return graph.remove_connection(self.state, user, other)

    def mutual_connections(self, other):
        user = self._need()
        if user is None:
            return self._denied()
        return graph.mutual_connections(self.state, user, other)

    def connection_degree(self, other):
        user = self._need()
        if user is None:
            return self._denied()
        return graph.connection_degree(self.state, user, other)

    def shortest_chain(self, other):
        user = self._need()
        if user is None:
            return self._denied()
        return graph.shortest_chain(self.state, user, other)

    def people_you_may_know(self, limit=config.SUGGESTION_LIMIT):
        user = self._need()
        if user is None:
            return self._denied()
        return graph.people_you_may_know(self.state, user, limit)

    def pending_requests(self):
        user = self._need()
        if user is None:
            return self._denied()
        return graph.pending_for(self.state, user)

    def create_post(self, text, community_id=None, media_paths=None):
        user = self._need()
        if user is None:
            return self._denied()
        return posts.create_post(self.state, user, text, community_id, media_paths)

    def delete_post(self, post_id):
        user = self._need()
        if user is None:
            return self._denied()
        return posts.delete_post(self.state, user, post_id)

    def own_posts(self):
        user = self._need()
        if user is None:
            return self._denied()
        return posts.own_posts(self.state, user)

    def explore_feed(self, page=0):
        return posts.explore_feed(self.state, page)

    def connections_feed(self, page=0):
        user = self._need()
        if user is None:
            return self._denied()
        return posts.connections_feed(self.state, user, page)

    def like_post(self, post_id):
        user = self._need()
        if user is None:
            return self._denied()
        target = self.state.posts.get(post_id)
        ok, msg = posts.like_post(self.state, user, post_id)
        if ok and target is not None and target.author != user:
            notifications.push(self.state, target.author, f"{user} liked your post")
        return ok, msg

    def unlike_post(self, post_id):
        user = self._need()
        if user is None:
            return self._denied()
        return posts.unlike_post(self.state, user, post_id)

    def likes_for(self, post_id):
        return posts.likes_for(self.state, post_id)

    def like_count(self, post_id):
        return posts.like_count(self.state, post_id)

    def add_comment(self, post_id, text, parent_id=None):
        user = self._need()
        if user is None:
            return self._denied()
        target = self.state.posts.get(post_id)
        result = posts.add_comment(self.state, user, post_id, text, parent_id)
        if result[0] and target is not None:
            if target.author != user:
                notifications.push(self.state, target.author, f"{user} commented on your post")
            if parent_id is not None:
                parent = self.state.comments.get(post_id, {}).get(parent_id)
                if parent is not None and parent.author not in (user, target.author):
                    notifications.push(self.state, parent.author, f"{user} replied to your comment")
        return result

    def comment_tree(self, post_id):
        return posts.comment_tree(self.state, post_id)

    def comment_count(self, post_id):
        return posts.comment_count(self.state, post_id)

    def delete_comment(self, post_id, comment_id):
        user = self._need()
        if user is None:
            return self._denied()
        return posts.delete_comment(self.state, user, post_id, comment_id)

    def trending_posts(self, limit=10):
        user = self._need()
        if user is None:
            return self._denied()
        return posts.trending_posts(self.state, user, limit)

    def save_post(self, post_id):
        user = self._need()
        if user is None:
            return self._denied()
        return posts.save_post(self.state, user, post_id)

    def unsave_post(self, post_id):
        user = self._need()
        if user is None:
            return self._denied()
        return posts.unsave_post(self.state, user, post_id)

    def saved_posts(self):
        user = self._need()
        if user is None:
            return self._denied()
        return posts.saved_posts(self.state, user)

    def report_post(self, post_id, reason):
        user = self._need()
        if user is None:
            return self._denied()
        return posts.report_post(self.state, user, post_id, reason)

    def moderation_queue(self):
        user = self._need()
        if user is None:
            return self._denied()
        return posts.moderation_queue(self.state, user)

    def review_report(self, report_id, action):
        user = self._need()
        if user is None:
            return self._denied()
        report = next((r for r in self.state.reports if r.report_id == report_id), None)
        target = self.state.posts.get(report.post_id) if report is not None else None
        ok, msg = posts.review_report(self.state, user, report_id, action)
        if ok and action == "remove" and target is not None:
            notifications.push(self.state, target.author, "Your post was removed after a moderation review")
        return ok, msg

    def notifications(self, unread_only=False):
        user = self._need()
        if user is None:
            return self._denied()
        return notifications.list_for(self.state, user, unread_only)

    def mark_notifications_read(self, notification_id=None):
        user = self._need()
        if user is None:
            return self._denied()
        return notifications.mark_read(self.state, user, notification_id)

    def unread_count(self):
        user = self._need()
        if user is None:
            return 0
        return notifications.unread_count(self.state, user)

    def send_message(self, receiver, text):
        user = self._need()
        if user is None:
            return self._denied()
        result = messages.send(self.state, user, receiver, text)
        if result[0]:
            notifications.push(self.state, receiver, f"{user} sent you a message")
        return result

    def conversation(self, other):
        user = self._need()
        if user is None:
            return self._denied()
        return messages.conversation(self.state, user, other)

    def conversations(self):
        user = self._need()
        if user is None:
            return self._denied()
        return messages.conversations(self.state, user)

    def mark_conversation_read(self, other):
        user = self._need()
        if user is None:
            return self._denied()
        return messages.mark_read(self.state, user, other)

    def unread_message_count(self):
        user = self._need()
        if user is None:
            return 0
        return messages.unread_count(self.state, user)

    def add_event(self, title, description, date, time_text, venue, community_id=None):
        user = self._need()
        if user is None:
            return self._denied()
        return events.add_event(self.state, user, title, description, date, time_text, venue, community_id)

    def events_on(self, date):
        return events.events_on(self.state, date)

    def upcoming_events(self, limit=10):
        return events.upcoming_events(self.state, limit)

    def upload_media(self, event_id, path):
        user = self._need()
        if user is None:
            return self._denied()
        return events.upload_media(self.state, user, event_id, path)

    def catalog_for(self, event_id):
        return events.catalog_for(self.state, event_id)

    def propose_pitch(self, title, description):
        user = self._need()
        if user is None:
            return self._denied()
        return events.propose_pitch(self.state, user, title, description)

    def pitches(self):
        user = self._need()
        if user is None:
            return self._denied()
        return events.pitches_for(self.state, user)

    def review_pitch(self, pitch_id, action):
        user = self._need()
        if user is None:
            return self._denied()
        pitch = next((p for p in self.state.pitches if p.pitch_id == pitch_id), None)
        result = events.review_pitch(self.state, user, pitch_id, action)
        if result[0] and pitch is not None:
            notifications.push(self.state, pitch.proposer, f"Your event pitch was {result[2].status}")
        return result

    def rsvp(self, event_id):
        user = self._need()
        if user is None:
            return self._denied()
        return events.rsvp(self.state, user, event_id)

    def cancel_rsvp(self, event_id):
        user = self._need()
        if user is None:
            return self._denied()
        return events.cancel_rsvp(self.state, user, event_id)

    def attendees(self, event_id):
        return events.attendees(self.state, event_id)

    def attendee_count(self, event_id):
        return events.attendee_count(self.state, event_id)

    def is_going(self, event_id):
        user = self._need()
        if user is None:
            return False
        return events.is_going(self.state, user, event_id)

    def create_club(self, name):
        user = self._need()
        if user is None:
            return self._denied()
        return communities.create_club(self.state, user, name)

    def create_group(self, name, visibility):
        user = self._need()
        if user is None:
            return self._denied()
        return communities.create_group(self.state, user, name, visibility)

    def assign_organiser(self, community_id, username):
        user = self._need()
        if user is None:
            return self._denied()
        ok, msg = communities.assign_organiser(self.state, user, community_id, username)
        if ok:
            notifications.push(self.state, username, f"You were made an organiser of a community by {user}")
        return ok, msg

    def join_community(self, community_id):
        user = self._need()
        if user is None:
            return self._denied()
        ok, msg = communities.join_community(self.state, user, community_id)
        community = self.state.communities.get(community_id)
        if ok and community is not None and community.visibility == "private":
            notifications.push(self.state, community.owner, f"{user} asked to join {community.name}")
        return ok, msg

    def approve_join(self, community_id, username):
        user = self._need()
        if user is None:
            return self._denied()
        ok, msg = communities.approve_join(self.state, user, community_id, username)
        if ok:
            notifications.push(self.state, username, f"Your request to join a community was approved")
        return ok, msg

    def reject_join(self, community_id, username):
        user = self._need()
        if user is None:
            return self._denied()
        return communities.reject_join(self.state, user, community_id, username)

    def leave_community(self, community_id):
        user = self._need()
        if user is None:
            return self._denied()
        return communities.leave_community(self.state, user, community_id)

    def community_members(self, community_id):
        return communities.community_members_list(self.state, community_id)

    def community_pending(self, community_id):
        return communities.community_pending_list(self.state, community_id)

    def community_feed(self, community_id, page=0):
        user = self._need()
        if user is None:
            return self._denied()
        return communities.community_feed(self.state, user, community_id, page)

    def post_to_community(self, community_id, text, media_paths=None):
        user = self._need()
        if user is None:
            return self._denied()
        return communities.post_to_community(self.state, user, community_id, text, media_paths)

    def list_communities(self):
        user = self._need()
        if user is None:
            return self._denied()
        return communities.list_communities(self.state, user)

    def get_user(self, username):
        return self.state.users.get(username)

    def get_post(self, post_id):
        return self.state.posts.get(post_id)

    def all_users(self):
        return sorted(self.state.users.values(), key=lambda user: user.username)

    def connections(self, username=None):
        target = username or self._need()
        if target is None:
            return self._denied()
        return graph.connections(self.state, target)

    def posts_by(self, username):
        return posts.own_posts(self.state, username)

    def get_event(self, event_id):
        return self.state.events.get(event_id)

    def all_events(self):
        return sorted(self.state.events.values(), key=lambda event: (event.date, event.time, event.event_id))

    def get_community(self, community_id):
        return self.state.communities.get(community_id)

    def is_liked(self, post_id):
        user = self._need()
        return bool(user and user in self.state.likes.get(post_id, set()))

    def is_saved(self, post_id):
        user = self._need()
        return bool(user and post_id in self.state.saved.get(user, {}))

    def stats(self):
        edges = sum(len(neighbours) for neighbours in self.state.adj.values()) // 2
        return {
            "users": len(self.state.users),
            "posts": len(self.state.posts),
            "connections": edges,
            "events": len(self.state.events),
            "communities": len(self.state.communities),
            "messages": len(self.state.messages),
        }

    def is_admin(self, username=None):
        return auth.is_admin(self.state, username or self._need())

    def community_role(self, community_id):
        user = self._need()
        if user is None:
            return None
        community = self.state.communities.get(community_id)
        if community is None:
            return None
        if community.owner == user:
            return "owner"
        if user in self.state.community_organisers.get(community_id, set()):
            return "organiser"
        if user in self.state.community_members.get(community_id, set()):
            return "member"
        if user in self.state.community_pending.get(community_id, set()):
            return "pending"
        return None

    def can_read_community(self, community_id):
        user = self._need()
        return bool(user and communities.can_read(self.state, user, community_id))
