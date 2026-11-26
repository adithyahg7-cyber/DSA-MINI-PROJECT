import time
from collections import deque

import config
import storage.db as db


def _ensure(state, username):
    state.adj.setdefault(username, set())
    state.pending_out.setdefault(username, {})
    state.pending_in.setdefault(username, {})


def _connected(state, a, b):
    return b in state.adj.get(a, set())


def send_request(state, sender, receiver):
    if sender not in state.users or receiver not in state.users:
        return False, "user not found"
    if sender == receiver:
        return False, "cannot connect to yourself"
    if _connected(state, sender, receiver):
        return False, "already connected"
    if receiver in state.pending_out.get(sender, {}):
        return False, "request already sent"
    if sender in state.pending_out.get(receiver, {}):
        return False, "request already pending"
    _ensure(state, sender)
    _ensure(state, receiver)
    ts = time.time()
    state.pending_out[sender][receiver] = ts
    state.pending_in[receiver][sender] = ts
    db.save_pending(sender, receiver, ts)
    return True, "request sent"


def accept_request(state, actor, sender):
    if actor not in state.pending_out.get(sender, {}):
        return False, "no pending request"
    _ensure(state, sender)
    _ensure(state, actor)
    state.pending_out[sender].pop(actor, None)
    state.pending_in[actor].pop(sender, None)
    db.delete_pending(sender, actor)
    state.adj[sender].add(actor)
    state.adj[actor].add(sender)
    db.save_connection(sender, actor)
    db.save_connection(actor, sender)
    return True, "request accepted"


def reject_request(state, actor, sender):
    if actor not in state.pending_out.get(sender, {}):
        return False, "no pending request"
    _ensure(state, sender)
    _ensure(state, actor)
    state.pending_out[sender].pop(actor, None)
    state.pending_in[actor].pop(sender, None)
    db.delete_pending(sender, actor)
    return True, "request rejected"


def cancel_request(state, sender, receiver):
    if receiver not in state.pending_out.get(sender, {}):
        return False, "no pending request"
    _ensure(state, sender)
    _ensure(state, receiver)
    state.pending_out[sender].pop(receiver, None)
    state.pending_in[receiver].pop(sender, None)
    db.delete_pending(sender, receiver)
    return True, "request cancelled"


def remove_connection(state, a, b):
    if not _connected(state, a, b):
        return False, "not connected"
    state.adj[a].discard(b)
    state.adj[b].discard(a)
    db.delete_connection(a, b)
    db.delete_connection(b, a)
    return True, "connection removed"


def mutual_connections(state, a, b):
    return sorted(state.adj.get(a, set()) & state.adj.get(b, set()))


def connection_degree(state, a, b):
    if a == b:
        return 0
    if _connected(state, a, b):
        return 1
    visited = {a}
    queue = deque([(a, 0)])
    while queue:
        node, depth = queue.popleft()
        if depth >= config.MAX_CHAIN_DEPTH:
            continue
        for neighbor in state.adj.get(node, set()):
            if neighbor in visited:
                continue
            if neighbor == b:
                return depth + 1
            visited.add(neighbor)
            queue.append((neighbor, depth + 1))
    return -1


def shortest_chain(state, a, b):
    if a == b:
        return [a]
    parent = {a: None}
    depth = {a: 0}
    queue = deque([a])
    while queue:
        node = queue.popleft()
        if depth[node] >= config.MAX_CHAIN_DEPTH:
            continue
        for neighbor in state.adj.get(node, set()):
            if neighbor in parent:
                continue
            parent[neighbor] = node
            depth[neighbor] = depth[node] + 1
            if neighbor == b:
                path = []
                current = b
                while current is not None:
                    path.append(current)
                    current = parent[current]
                path.reverse()
                return path
            queue.append(neighbor)
    return []


def people_you_may_know(state, username, limit=config.SUGGESTION_LIMIT):
    mine = state.adj.get(username, set())
    candidates = set()
    visited = {username}
    queue = deque([(username, 0)])
    while queue:
        node, depth = queue.popleft()
        if depth >= 2:
            continue
        for neighbor in state.adj.get(node, set()):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            if depth + 1 == 2:
                candidates.add(neighbor)
            queue.append((neighbor, depth + 1))
    candidates -= mine
    candidates.discard(username)
    scored = []
    for candidate in candidates:
        other = state.adj.get(candidate, set())
        union = other | mine
        score = len(other & mine) / len(union) if union else 0.0
        scored.append((candidate, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [(candidate, round(score, 3)) for candidate, score in scored[:limit]]


def pending_for(state, username):
    incoming = [(other, ts) for other, ts in state.pending_in.get(username, {}).items()]
    outgoing = [(other, ts) for other, ts in state.pending_out.get(username, {}).items()]
    incoming.sort(key=lambda item: (item[1], item[0]))
    outgoing.sort(key=lambda item: (item[1], item[0]))
    return incoming, outgoing


def connections(state, username):
    return sorted(state.adj.get(username, set()))
