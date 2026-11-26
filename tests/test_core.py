import os
import shutil
import tempfile
import unittest

import config
from core.engine import Engine


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = os.path.join(self.folder, "test.db")
        self.engine = Engine(self.path)
        self.engine.signup("alice", "Alice Kumar", "secret1")
        self.engine.signup("bob", "Bob Rao", "secret1")
        self.engine.signup("carol", "Carol Das", "secret1")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def login(self, username, password="secret1"):
        ok, _ = self.engine.login(username, password)
        self.assertTrue(ok)

    def connect(self, a, b):
        self.login(a)
        self.assertTrue(self.engine.send_request(b)[0])
        self.login(b)
        self.assertTrue(self.engine.accept_request(a)[0])


class AccountTests(BaseCase):
    def test_signup_login_and_trie(self):
        self.assertIn("alice", self.engine.search_users("ali"))
        self.assertIn("carol", self.engine.search_users("das"))
        self.assertFalse(self.engine.signup("alice", "Other", "secret1")[0])
        self.assertFalse(self.engine.signup("x", "X", "secret1")[0])
        self.assertFalse(self.engine.login("alice", "wrong")[0])
        self.login("alice")
        self.assertEqual(self.engine.me, "alice")

    def test_roles_and_last_admin_guard(self):
        self.assertTrue(self.engine.login(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)[0])
        self.assertTrue(self.engine.set_role("alice", "organiser")[0])
        self.assertEqual(self.engine.state.users["alice"].role, "organiser")
        self.assertFalse(self.engine.set_role(config.ADMIN_USERNAME, "student")[0])
        self.assertTrue(self.engine.set_role("alice", "admin")[0])
        self.assertTrue(self.engine.set_role(config.ADMIN_USERNAME, "student")[0])
        self.assertEqual(len(self.engine.role_log()), 3)

    def test_signup_ignores_role_input(self):
        self.engine.signup("dave", "Dave", "secret1", "admin")
        self.assertEqual(self.engine.state.users["dave"].role, "student")


class GraphTests(BaseCase):
    def test_connect_and_degree(self):
        self.connect("alice", "bob")
        self.login("alice")
        self.assertEqual(self.engine.connection_degree("bob"), 1)
        self.assertEqual(self.engine.connection_degree("alice"), 0)

    def test_second_degree_chain_and_suggestions(self):
        self.connect("alice", "bob")
        self.connect("bob", "carol")
        self.login("alice")
        self.assertEqual(self.engine.connection_degree("carol"), 2)
        self.assertEqual(self.engine.shortest_chain("carol"), ["alice", "bob", "carol"])
        suggestions = dict(self.engine.people_you_may_know())
        self.assertIn("carol", suggestions)

    def test_mutual_and_remove(self):
        self.connect("alice", "bob")
        self.connect("alice", "carol")
        self.connect("bob", "carol")
        self.login("alice")
        self.assertEqual(self.engine.mutual_connections("bob"), ["carol"])
        self.assertTrue(self.engine.remove_connection("bob")[0])
        self.assertEqual(self.engine.connection_degree("bob"), 2)

    def test_request_lifecycle(self):
        self.login("alice")
        self.assertTrue(self.engine.send_request("bob")[0])
        self.assertFalse(self.engine.send_request("bob")[0])
        self.login("bob")
        incoming, _ = self.engine.pending_requests()
        self.assertIn("alice", [name for name, _ in incoming])
        self.assertTrue(self.engine.reject_request("alice")[0])
        self.login("alice")
        self.assertTrue(self.engine.send_request("bob")[0])
        self.assertTrue(self.engine.cancel_request("bob")[0])


class FeedTests(BaseCase):
    def test_explore_and_connections_feed(self):
        self.connect("alice", "bob")
        self.login("bob")
        for text in ("one", "two", "three"):
            self.assertTrue(self.engine.create_post(text)[0])
        self.login("alice")
        feed = self.engine.connections_feed()
        self.assertEqual({post.text for post in feed}, {"one", "two", "three"})
        explore = self.engine.explore_feed()
        self.assertEqual({post.text for post in explore}, {"one", "two", "three"})

    def test_trending_ranks_likes_and_comments(self):
        self.connect("alice", "bob")
        self.login("bob")
        first = self.engine.create_post("first")[2]
        second = self.engine.create_post("second")[2]
        self.login("alice")
        self.engine.like_post(first.post_id)
        self.engine.add_comment(second.post_id, "nice")
        ranked = self.engine.trending_posts()
        self.assertEqual(len(ranked), 2)
        self.assertGreater(ranked[0][1], 0)

    def test_saved_and_deleted_post(self):
        self.login("alice")
        post = self.engine.create_post("keep me")[2]
        self.assertTrue(self.engine.save_post(post.post_id)[0])
        self.assertEqual(len(self.engine.saved_posts()), 1)
        self.engine.delete_post(post.post_id)
        self.assertEqual(self.engine.saved_posts(), [])


class CommentTests(BaseCase):
    def test_comment_tree(self):
        self.login("alice")
        post = self.engine.create_post("hello")[2]
        self.login("bob")
        root = self.engine.add_comment(post.post_id, "root")[2]
        self.engine.add_comment(post.post_id, "reply", root.comment_id)
        tree = self.engine.comment_tree(post.post_id)
        self.assertEqual(len(tree), 1)
        self.assertEqual(len(tree[0]["replies"]), 1)


class ReportTests(BaseCase):
    def test_report_and_moderation(self):
        self.login("alice")
        post = self.engine.create_post("bad post")[2]
        self.login("bob")
        self.assertTrue(self.engine.report_post(post.post_id, "spam")[0])
        self.assertFalse(self.engine.report_post(post.post_id, "spam again")[0])
        self.assertFalse(self.engine.moderation_queue()[0])
        self.engine.login(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
        ok, _, queue = self.engine.moderation_queue()
        self.assertTrue(ok)
        self.assertEqual(len(queue), 1)
        self.assertTrue(self.engine.review_report(queue[0].report_id, "remove")[0])
        self.assertNotIn(post.post_id, self.engine.state.posts)


class EventTests(BaseCase):
    def test_event_catalog_pitch_and_rsvp(self):
        self.engine.login(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
        ok, _, event = self.engine.add_event("Hackathon", "Build", "2026-12-01", "10:00", "Hall A")
        self.assertTrue(ok)
        self.assertEqual(len(self.engine.upcoming_events()), 1)
        self.assertTrue(self.engine.upload_media(event.event_id, "uploads/a.png")[0])
        self.assertEqual(len(self.engine.catalog_for(event.event_id)), 1)
        self.login("alice")
        self.assertTrue(self.engine.rsvp(event.event_id)[0])
        self.assertEqual(self.engine.attendee_count(event.event_id), 1)
        self.assertTrue(self.engine.is_going(event.event_id))
        self.assertTrue(self.engine.cancel_rsvp(event.event_id)[0])

    def test_pitch_review(self):
        self.login("alice")
        pitch = self.engine.propose_pitch("Robotics night", "Show robots")[2]
        self.assertFalse(self.engine.review_pitch(pitch.pitch_id, "approve")[0])
        self.engine.login(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
        ok, _, reviewed = self.engine.review_pitch(pitch.pitch_id, "approve")
        self.assertTrue(ok)
        self.assertEqual(reviewed.status, "approved")


class CommunityTests(BaseCase):
    def test_private_group_join_flow(self):
        self.login("alice")
        ok, _, group = self.engine.create_group("Study Group", "private")
        self.assertTrue(ok)
        self.login("bob")
        self.assertTrue(self.engine.join_community(group.community_id)[0])
        self.assertFalse(self.engine.community_feed(group.community_id)[0])
        self.login("alice")
        self.assertTrue(self.engine.approve_join(group.community_id, "bob")[0])
        self.login("bob")
        self.assertTrue(self.engine.community_feed(group.community_id)[0])
        self.assertTrue(self.engine.post_to_community(group.community_id, "hello group")[0])
        self.assertEqual(len(self.engine.community_feed(group.community_id)[2]), 1)

    def test_club_requires_membership(self):
        self.engine.login(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
        ok, _, club = self.engine.create_club("Coding Club")
        self.assertTrue(ok)
        self.login("alice")
        self.assertFalse(self.engine.community_feed(club.community_id)[0])
        self.assertTrue(self.engine.join_community(club.community_id)[0])
        self.assertTrue(self.engine.community_feed(club.community_id)[0])


class PersistenceTests(BaseCase):
    def test_reload_rebuilds_state(self):
        self.connect("alice", "bob")
        self.engine.login("bob", "secret1")
        post = self.engine.create_post("persisted")[2]
        self.login("alice")
        self.engine.like_post(post.post_id)

        fresh = Engine(self.path)
        self.assertIn("alice", fresh.state.users)
        self.assertIn("bob", fresh.state.adj["alice"])
        self.assertIn(post.post_id, fresh.state.posts)
        self.assertIn("alice", fresh.state.likes[post.post_id])
        self.assertIn("bob", fresh.search_users("bob"))
        self.assertIn("persisted", fresh.explore_feed()[0].text)


if __name__ == "__main__":
    unittest.main()
