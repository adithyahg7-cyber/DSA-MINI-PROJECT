import datetime
import heapq
import time

import config
from core.models import Event, Media, Pitch
from storage import db


def _role_allows(state, username):
    user = state.users.get(username)
    if user is None:
        return False
    return user.role in ("organiser", "admin")


def add_event(state, actor, title, description, date, time_text, venue, community_id=None):
    if not _role_allows(state, actor):
        return False, "Only organisers and admins can create events", None
    if not title or not title.strip():
        return False, "Title is required", None
    if not venue or not venue.strip():
        return False, "Venue is required", None
    if not date or not date.strip():
        return False, "Date is required", None
    try:
        parsed = datetime.date.fromisoformat(date)
    except (TypeError, ValueError):
        return False, "Date must be in YYYY-MM-DD format", None
    if parsed.isoformat() != date:
        return False, "Date must be in YYYY-MM-DD format", None
    event_id = state.next_id("event")
    event = Event(
        event_id,
        title.strip(),
        description,
        date,
        time_text,
        venue.strip(),
        actor,
        community_id,
    )
    state.events[event_id] = event
    state.events_by_date.setdefault(date, []).append(event_id)
    heapq.heappush(state.event_heap, (date, event_id))
    db.save_event(event)
    return True, "Event created", event


def events_on(state, date):
    event_ids = state.events_by_date.get(date, [])
    events = [state.events[event_id] for event_id in event_ids if event_id in state.events]
    events.sort(key=lambda event: (event.time, event.event_id))
    return events


def upcoming_events(state, limit=10, from_date=None):
    if from_date is None:
        from_date = datetime.date.today().isoformat()
    if limit is None or limit <= 0:
        return []
    heap = list(state.event_heap)
    heapq.heapify(heap)
    results = []
    while heap and len(results) < limit:
        date_value, event_id = heapq.heappop(heap)
        event = state.events.get(event_id)
        if event is None:
            continue
        if date_value < from_date:
            continue
        results.append(event)
    return results


def upload_media(state, actor, event_id, path):
    if not _role_allows(state, actor):
        return False, "Only organisers and admins can upload media", None
    if event_id not in state.events:
        return False, "Event not found", None
    if not path or not path.strip():
        return False, "Path is required", None
    media_id = state.next_id("media")
    media = Media(media_id, event_id, path, actor, time.time())
    state.catalog.setdefault(event_id, []).append(media)
    db.save_media(media)
    return True, "Media uploaded", media


def catalog_for(state, event_id):
    media = list(state.catalog.get(event_id, []))
    media.sort(key=lambda item: item.media_id)
    return media


def propose_pitch(state, proposer, title, description):
    if proposer not in state.users:
        return False, "User not found", None
    if not title or not title.strip():
        return False, "Title is required", None
    if not description or not description.strip():
        return False, "Description is required", None
    pitch_id = state.next_id("pitch")
    pitch = Pitch(
        pitch_id,
        proposer,
        title.strip(),
        description.strip(),
        "pending",
        time.time(),
    )
    state.pitches.append(pitch)
    db.save_pitch(pitch)
    return True, "Pitch submitted", pitch


def pitches_for(state, actor):
    if actor not in state.users:
        return False, "User not found", []
    newest_first = list(reversed(state.pitches))
    user = state.users[actor]
    if user.role == "admin":
        return True, "Pitches loaded", newest_first
    mine = [pitch for pitch in newest_first if pitch.proposer == actor]
    return True, "Pitches loaded", mine


def review_pitch(state, actor, pitch_id, action):
    user = state.users.get(actor)
    if user is None or user.role != "admin":
        return False, "Only admins can review pitches", None
    if action not in ("approve", "reject"):
        return False, "Action must be approve or reject", None
    target = None
    for pitch in state.pitches:
        if pitch.pitch_id == pitch_id:
            target = pitch
            break
    if target is None:
        return False, "Pitch not found", None
    if target.status != "pending":
        return False, "Pitch already reviewed", None
    target.status = "approved" if action == "approve" else "rejected"
    target.decided_by = actor
    target.decided_at = time.time()
    db.save_pitch(target)
    return True, "Pitch " + target.status, target


def rsvp(state, username, event_id):
    if event_id not in state.events:
        return False, "Event not found"
    if username not in state.users:
        return False, "User not found"
    going = state.rsvps.setdefault(event_id, set())
    if username in going:
        return False, "Already registered for this event"
    going.add(username)
    state.user_rsvps.setdefault(username, set()).add(event_id)
    db.save_rsvp(event_id, username)
    return True, "RSVP confirmed"


def cancel_rsvp(state, username, event_id):
    if event_id not in state.events:
        return False, "Event not found"
    if username not in state.users:
        return False, "User not found"
    going = state.rsvps.get(event_id)
    if not going or username not in going:
        return False, "You are not registered for this event"
    going.discard(username)
    user_events = state.user_rsvps.get(username)
    if user_events is not None:
        user_events.discard(event_id)
    db.delete_rsvp(event_id, username)
    return True, "RSVP cancelled"


def attendees(state, event_id):
    return set(state.rsvps.get(event_id, set()))


def attendee_count(state, event_id):
    return len(state.rsvps.get(event_id, set()))


def is_going(state, username, event_id):
    return username in state.rsvps.get(event_id, set())
