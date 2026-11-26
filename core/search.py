import config


class Trie:
    def __init__(self):
        self.root = {"children": {}, "users": set()}

    def insert(self, word, username):
        node = self.root
        for char in word.lower():
            children = node["children"]
            if char not in children:
                children[char] = {"children": {}, "users": set()}
            node = children[char]
        node["users"].add(username)

    def search(self, prefix, limit):
        if limit <= 0:
            return []
        node = self.root
        for char in prefix.lower():
            node = node["children"].get(char)
            if node is None:
                return []
        found = set()

        def walk(current):
            if len(found) >= limit:
                return
            found.update(current["users"])
            for char in sorted(current["children"]):
                if len(found) >= limit:
                    return
                walk(current["children"][char])

        walk(node)
        return sorted(found)[:limit]


def index_user(state, user):
    state.trie.insert(user.username, user.username)
    for word in user.name.split():
        state.trie.insert(word.lower(), user.username)


def rebuild_trie(state):
    state.trie = Trie()
    for user in state.users.values():
        index_user(state, user)


def search_users(state, prefix, limit=config.SEARCH_LIMIT):
    return state.trie.search(prefix, limit)
