import time

from core import graph
from core.models import Message
from storage import db


def _ordered(messages):
    return sorted(messages, key=lambda item: (item.created_at, item.message_id))


def send(state, sender, receiver, text):
    if receiver not in state.users:
        return False, "User not found.", None
    if sender not in state.users:
        return False, "Sign in first.", None
    if receiver == sender:
        return False, "You cannot message yourself.", None
    if receiver not in graph.connections(state, sender):
        return False, "Connect with this person before messaging them.", None
    if not isinstance(text, str) or not text.strip():
        return False, "Message cannot be empty.", None
    message = Message(
        state.next_id("message"),
        sender,
        receiver,
        text.strip(),
        time.time(),
        False,
    )
    state.messages.append(message)
    db.save_message(message)
    return True, "Message sent.", message


def conversation(state, username, other):
    if other not in state.users:
        return False, "User not found.", []
    if other not in graph.connections(state, username):
        return False, "You are not connected with this person.", []
    messages = [
        item
        for item in state.messages
        if {item.sender, item.receiver} == {username, other}
    ]
    return True, "Conversation loaded.", _ordered(messages)


def mark_read(state, username, other):
    changed = False
    for message in state.messages:
        if message.sender == other and message.receiver == username and not message.is_read:
            message.is_read = True
            db.mark_message_read(message.message_id)
            changed = True
    return True, "Conversation marked as read." if changed else "No new messages."


def conversations(state, username):
    peers = graph.connections(state, username)
    rows = []
    for peer in peers:
        user = state.users.get(peer)
        if user is None:
            continue
        thread = [
            item
            for item in state.messages
            if {item.sender, item.receiver} == {username, peer}
        ]
        if not thread:
            continue
        last = _ordered(thread)[-1]
        unread = sum(
            1
            for item in thread
            if item.sender == peer and item.receiver == username and not item.is_read
        )
        rows.append({"user": user, "last": last, "unread": unread})
    rows.sort(key=lambda row: (row["last"].created_at, row["last"].message_id), reverse=True)
    return True, "Conversations loaded.", rows


def unread_count(state, username):
    return sum(
        1
        for item in state.messages
        if item.receiver == username and not item.is_read
    )
