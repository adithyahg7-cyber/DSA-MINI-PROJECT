import time
from collections import deque

import storage.db as db
from core.models import Notification


def push(state, username, text):
    note = Notification(state.next_id("notification"), username, text, time.time())
    state.notifications.setdefault(username, deque()).append(note)
    state.unread[username] = state.unread.get(username, 0) + 1
    db.save_notification(note)
    return note


def list_for(state, username, unread_only=False):
    notes = list(state.notifications.get(username, deque()))
    notes.reverse()
    if unread_only:
        notes = [note for note in notes if not note.is_read]
    return notes


def unread_count(state, username):
    return state.unread.get(username, 0)


def mark_read(state, username, notification_id=None):
    notes = state.notifications.get(username)
    if notes is None:
        notes = deque()
        state.notifications[username] = notes
    if notification_id is not None:
        for note in notes:
            if note.notification_id == notification_id:
                note.is_read = True
                db.mark_notification_read(notification_id)
                state.unread[username] = sum(1 for item in notes if not item.is_read)
                return True, "notification marked as read"
        return False, "notification not found"
    for note in notes:
        if not note.is_read:
            note.is_read = True
            db.mark_notification_read(note.notification_id)
    state.unread[username] = sum(1 for item in notes if not item.is_read)
    return True, "all notifications marked as read"
