from collections import deque

from core.search import Trie


class State:
    def __init__(self):
        self.reset()

    def reset(self):
        self.users = {}
        self.adj = {}
        self.pending_out = {}
        self.pending_in = {}

        self.posts = {}
        self.user_posts = {}
        self.all_posts = []
        self.post_media = {}

        self.trie = Trie()

        self.likes = {}
        self.comments = {}

        self.notifications = {}
        self.unread = {}

        self.messages = []

        self.events = {}
        self.events_by_date = {}
        self.event_heap = []
        self.catalog = {}
        self.pitches = deque()
        self.rsvps = {}
        self.user_rsvps = {}

        self.saved = {}
        self.reports = deque()
        self.report_keys = set()

        self.communities = {}
        self.community_members = {}
        self.community_organisers = {}
        self.community_pending = {}
        self.community_posts = {}
        self.user_communities = {}

        self.role_log = []

        self.counters = {
            "post": 1,
            "comment": 1,
            "notification": 1,
            "event": 1,
            "media": 1,
            "post_media": 1,
            "message": 1,
            "pitch": 1,
            "community": 1,
            "report": 1,
            "role_log": 1,
        }

        self.current_user = None

    def next_id(self, kind):
        value = self.counters.get(kind, 1)
        self.counters[kind] = value + 1
        return value
