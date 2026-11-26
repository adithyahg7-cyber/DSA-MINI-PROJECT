import os
import tempfile
import unittest

import config
from web.app import create_app

import storage.db as db


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test_web.db")
        self.app = create_app(self.db_path, testing=True)
        self.app.config.update(SERVER_NAME="localhost")
        self.client = self.app.test_client()

    def tearDown(self):
        db.set_db_path(config.DB_PATH)
        self.tmp.cleanup()

    def signup(self, client, username, name, password="secret123"):
        return client.post(
            "/signup",
            data={"username": username, "name": name, "password": password},
            follow_redirects=True,
        )

    def login(self, client, username, password="secret123"):
        return client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )

    def test_landing_and_auth_pages(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"CU-Kizuna", response.data)
        self.assertEqual(self.client.get("/login").status_code, 200)
        self.assertEqual(self.client.get("/signup").status_code, 200)

    def test_signup_creates_session_and_feed(self):
        response = self.signup(self.client, "ananya", "Ananya Rao")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ananya", response.data)
        self.assertEqual(self.client.get("/feed").status_code, 200)
        self.assertEqual(self.client.get("/network").status_code, 200)

    def test_logout_blocks_private_pages(self):
        self.signup(self.client, "kabir", "Kabir Shah")
        response = self.client.post("/logout", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        response = self.client.get("/feed")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_post_like_comment_save_flow(self):
        self.signup(self.client, "meera", "Meera Iyer")
        self.client.post("/posts", data={"text": "First post from the web"}, follow_redirects=True)
        feed = self.client.get("/feed")
        self.assertIn(b"First post from the web", feed.data)
        self.client.post("/posts/1/like", data={}, follow_redirects=True)
        self.client.post("/posts/1/comment", data={"text": "Nice one"}, follow_redirects=True)
        self.client.post("/posts/1/save", data={}, follow_redirects=True)
        page = self.client.get("/feed")
        self.assertIn(b"Nice one", page.data)
        saved = self.client.get("/saved")
        self.assertIn(b"First post from the web", saved.data)

    def test_connections_between_two_users(self):
        self.signup(self.client, "riya", "Riya Nair")
        other = self.app.test_client()
        self.signup(other, "arjun", "Arjun Menon")
        self.client.post("/network/request/arjun", follow_redirects=True)
        pending = other.get("/network")
        self.assertIn(b"riya", pending.data)
        other.post("/network/accept/riya", follow_redirects=True)
        mine = self.client.get("/network")
        self.assertIn(b"arjun", mine.data)
        self.client.post("/posts", data={"text": "Visible to connections"}, follow_redirects=True)
        feed = other.get("/feed?tab=connections")
        self.assertIn(b"Visible to connections", feed.data)

    def test_search_prefix(self):
        self.signup(self.client, "ananya", "Ananya Rao")
        found = self.client.get("/search?q=anan")
        self.assertIn(b"Ananya Rao", found.data)
        missing = self.client.get("/search?q=zzz")
        self.assertIn(b"No matches", missing.data)

    def test_profile_and_settings(self):
        self.signup(self.client, "dev", "Dev Patel")
        profile = self.client.get("/u/dev")
        self.assertEqual(profile.status_code, 200)
        self.client.post(
            "/settings",
            data={"kind": "profile", "name": "Dev P", "bio": "Backend person"},
            follow_redirects=True,
        )
        updated = self.client.get("/u/dev")
        self.assertIn(b"Dev P", updated.data)
        self.assertIn(b"Backend person", updated.data)
        self.client.post(
            "/settings",
            data={"kind": "username", "new_username": "devpatel"},
            follow_redirects=True,
        )
        self.assertEqual(self.client.get("/u/devpatel").status_code, 200)

    def test_events_and_rsvp(self):
        self.login(self.client, "admin", "admin123")
        self.client.post(
            "/events/add",
            data={
                "title": "Hack night",
                "description": "Build things",
                "date": "2026-12-10",
                "time": "18:00",
                "venue": "Lab 2",
            },
            follow_redirects=True,
        )
        listing = self.client.get("/events")
        self.assertIn(b"Hack night", listing.data)
        self.client.post("/events/1/rsvp", follow_redirects=True)
        detail = self.client.get("/events/1")
        self.assertIn(b"You are going", detail.data)

    def test_communities_public_and_private(self):
        self.login(self.client, "admin", "admin123")
        self.client.post("/communities/create", data={"kind": "club", "name": "Robotics Club"}, follow_redirects=True)
        listing = self.client.get("/communities")
        self.assertIn(b"Robotics Club", listing.data)
        self.client.post("/communities/1/join", follow_redirects=True)
        detail = self.client.get("/communities/1")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"Robotics Club", detail.data)

    def test_private_group_requires_approval(self):
        self.signup(self.client, "owner1", "Owner One")
        self.client.post(
            "/communities/create",
            data={"kind": "group", "name": "Quiet Room", "visibility": "private"},
            follow_redirects=True,
        )
        outsider = self.app.test_client()
        self.signup(outsider, "outsider", "Out Sider")
        outsider.post("/communities/1/join", follow_redirects=True)
        blocked = outsider.get("/communities/1")
        self.assertIn(b"cannot read", blocked.data)
        self.client.post("/communities/1/approve/outsider", follow_redirects=True)
        allowed = outsider.get("/communities/1")
        self.assertNotIn(b"cannot read", allowed.data)

    def test_admin_role_change_and_permissions(self):
        self.login(self.client, "admin", "admin123")
        self.signup(self.app.test_client(), "stu", "Student One")
        response = self.client.post(
            "/admin/role",
            data={"username": "stu", "role": "organiser"},
            follow_redirects=True,
        )
        self.assertIn(b"role updated", response.data)
        student = self.app.test_client()
        self.login(student, "stu")
        forbidden = student.get("/admin")
        self.assertEqual(forbidden.status_code, 403)

    def test_404_for_unknown_profile(self):
        self.login(self.client, "admin", "admin123")
        response = self.client.get("/u/ghost")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
