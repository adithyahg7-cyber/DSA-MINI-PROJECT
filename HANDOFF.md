# HANDOFF: CU-Kizuna (DSA Mini Project)

Last updated: 2026-11-26
Read this first if the chat is lost or tokens run out.

## What this is

CU-Kizuna is a social network for the DSA mini project (Chanakya University, B.Tech CS&AI).
Python 3.13 + Flask 3.1 + SQLite. Submission deadline: 27-11-2026.

Hard rules from `PROJECT_SPEC.md`:
- Graph, feed, and search logic runs in Python on in-memory structures, never in SQL.
- SQLite only stores rows. `storage/loader.py` rebuilds memory at startup.
- Core engine is separate from the UI. The UI calls `core.engine.Engine` only.
- Permission checks live in the engine/modules, not only in templates.
- Accepted connection = undirected edge (two adjacency insertions).
- Pending request = directed edge in `pending_out` / `pending_in`.
- No comments in code; names are self-explanatory.

## Status

- Backend: complete. 17/17 core tests pass. Console harness works end to end.
- Frontend: complete. 12/12 web tests pass. All pages below are implemented.
- Redesign pass: complete. Campus Amber light/dark theme, post media, profile photos,
  calendar month view, DMs, catalog lightbox, AJAX post actions, comment deletion,
  and admin-only graph tools are all wired and smoke-tested.
- Demo data: seeded by `seed_demo.py`. It exits without changes if demo users exist.
- Persistence: verified across restart, including new media/message tables.
- Repository: https://github.com/vaibavl/CU-Kizuna (public, `main` branch).
- Remaining work: submission polish only (report, DS log, viva preparation).
  No new features are required.

## Run

```powershell
# optional, once
python seed_demo.py

# web app
python run_web.py
# http://127.0.0.1:5000

# console harness
python main.py

# tests
python -m unittest tests.test_core -v
python -m unittest tests.test_web -v
```

Admin seed from `config.py`: `admin` / `admin123`.
Every demo account uses `campus123`.

## Demo accounts

| Username | Name | Role |
|---|---|---|
| `ananya` | Ananya Rao | student |
| `riya` | Riya Nair | organiser |
| `kabir` | Kabir Shah | student |
| `meera` | Meera Iyer | organiser |
| `arjun` | Arjun Menon | student |
| `zoya` | Zoya Khan | student |
| `pranav` | Pranav Desai | student |

## File map

```text
config.py                 paths, admin seed, PAGE_SIZE=10, TRENDING_DAYS=7, MAX_CHAIN_DEPTH=3
requirements.txt          flask>=3.0
PROJECT_SPEC.md           original spec
DS_Feature_Log.pdf        DS log deliverable
Mini Project - DSA (CSAI-EVE-EECS).pdf   course brief
README.md                 setup, features, credentials
PROGRESS.md               human checklist (updated through redesign pass)
PROGRESS.json             data for the TUI sidebar progress plugin
HANDOFF.md                this file

core/
  models.py               dataclasses: User(avatar) Post(media) PostMedia Comment Notification
                          Event Media Message Pitch Community Report
  state.py                ONE State object with every dict/set/list/heap/trie/counter
  search.py               Trie, index_user, rebuild_trie, search_users
  auth.py                 salted PBKDF2, signup/login/logout, seed_admin, set_role, role log,
                          settings, avatar update, rename across all structures
  graph.py                adjacency, pending lifecycle, BFS degree/chain, mutuals, Jaccard, connections()
  notifications.py        deque per user + unread counter
  posts.py                posts with media, feeds, likes, comments, recursive comment delete,
                          trending, saved, reports/moderation
  messages.py             connected-user DMs, ordered conversations, mark-read, unread count
  events.py               calendar dict + min-heap, catalog, pitches, RSVP
  communities.py          clubs + public/private groups, joins, feeds, media posts
  engine.py               facade; all UI calls go here; creates notifications after actions
storage/
  db.py                   19-table schema + avatar migration + save/delete/rename/query helpers
  loader.py               rebuild State from SQLite, including post media and messages
web/
  app.py                  create_app(), routes, session actor, uploads, AJAX actions, error pages
  templates/              base shell landing auth feed _post _comments _comments_fragment
                          network search profile settings saved notifications events event_detail
                          calendar messages communities community_detail admin error
  static/css/app.css      Campus Amber light/dark design system
  static/img/             logo.jpg (user logo; also post-login background watermark), campus-background.webp, amber-watermark.svg
  static/js/app.js        theme toggle, lightbox, AJAX post actions, animations
tests/
  test_core.py            17 tests, all passing
  test_web.py             12 tests, all passing
main.py                   console menu covering every feature
run_web.py                starts Flask
seed_demo.py              demo users, posts, events, communities, pitches
```

## State object (`core/state.py`)

- `users: dict[username -> User]` (`User.avatar` holds an `/uploads/...` path or `None`)
- `adj: dict[username -> set[username]]`
- `pending_out / pending_in: dict[username -> dict[other -> ts]]`
- `posts: dict[id -> Post]`, `user_posts: dict[username -> list[id]]`, `all_posts: list[id]` (oldest first)
- `post_media: dict[post_id -> list[PostMedia]]`; each `Post` also has a `media` list
- `trie`
- `likes: dict[post_id -> set[username]]`, `comments: dict[post_id -> dict[comment_id -> Comment]]`
- `notifications: dict[username -> deque]`, `unread: dict[username -> int]`
- `messages: list[Message]` (ordered by `created_at, message_id` during load)
- `events: dict[id -> Event]`, `events_by_date: dict[date -> list[id]]`, `event_heap: list[(date, id)]`, `catalog: dict[event_id -> list[Media]]`
- `pitches: deque[Pitch]`
- `rsvps: dict[event_id -> set[username]]`, `user_rsvps: dict[username -> set[event_id]]`
- `saved: dict[username -> dict[post_id -> ts]]`
- `reports: deque[Report]`, `report_keys: set[(post_id, reporter)]`
- `communities: dict[id -> Community]`
- `community_members / community_organisers / community_pending: dict[id -> set[username]]`
- `community_posts: dict[id -> list[post_id]]`, `user_communities: dict[username -> set[id]]`
- `role_log: list[dict]`
- `counters: dict[kind -> next id]`, `current_user: str|None`

## SQLite tables (`storage/db.py`)

users (`avatar` column), connections, pending, posts, comments, likes, notifications, events,
media, post_media, messages, pitches, communities (column `kind` = club/group),
community_members (role = member/organiser/pending), community_posts, role_log, rsvps,
saved_posts, reports.

`init_db()` also adds the `users.avatar` column to older databases that were created
before the redesign.

## Where the new stuff is stored

| Feature | In memory | SQLite | Files / browser |
|---|---|---|---|
| Post photos/videos | `Post.media` + `state.post_media` | `post_media` table | `uploads/`; path stored as `/uploads/<name>` |
| Profile photo | `User.avatar` | `users.avatar` | `uploads/`; path stored as `/uploads/<name>` |
| Event catalog | `state.catalog` | `media` table | `uploads/`; shown through lightbox with download + X |
| Direct messages | `state.messages` | `messages` table (`is_read`) | no separate file storage |
| Comment deletion | removed from `state.comments` recursively | rows deleted from `comments` | no separate file storage |
| Calendar month | derived from `state.events` | `events` table | no new table |
| Theme | `document.documentElement.dataset.theme` | not stored server-side | `localStorage["kizuna-theme"]` |

## Engine API (the only thing the UI should call)

Auth: `signup login logout seed_admin set_role role_log change_password update_profile
update_avatar change_username`
Search: `search_users(prefix, limit)`
Graph: `send_request accept_request reject_request cancel_request remove_connection mutual_connections
connection_degree shortest_chain people_you_may_know pending_requests connections`
Posts: `create_post(text, community_id=None, media_paths=None) delete_post own_posts posts_by
explore_feed connections_feed like_post unlike_post likes_for like_count add_comment comment_tree
comment_count delete_comment trending_posts save_post unsave_post saved_posts report_post
moderation_queue review_report`
Messages: `send_message(receiver, text) conversation(other) conversations()
mark_conversation_read(other) unread_message_count()`
Notifications: `notifications mark_notifications_read unread_count`
Events: `add_event events_on upcoming_events upload_media catalog_for propose_pitch pitches
review_pitch rsvp cancel_rsvp attendees attendee_count is_going`
Communities: `create_club create_group assign_organiser join_community approve_join reject_join
leave_community community_members community_pending community_feed
post_to_community(community_id, text, media_paths=None) list_communities`
Helpers: `get_user get_post all_users all_events get_event get_community is_liked is_saved
is_admin community_role can_read_community stats`

Return conventions: actions return `(ok: bool, message: str)`; posts/comments/events/messages
return a third object; feeds return lists; `moderation_queue`, `pitches`, `conversations`
and DM helpers return `(ok, msg, list)`.

Web-only routes worth knowing:
- `GET /calendar?year=...&month=...&day=...` builds the month grid from `Engine.all_events()`.
- `GET /posts/<id>/comments` returns the partial comment HTML used by AJAX refresh.
- AJAX post actions send header `X-Requested-With: fetch` and receive JSON instead of a redirect.
- `GET /messages` and `GET /messages/<username>` are the DM inbox and thread.
- Graph tools are only rendered on `/admin`; `/network` no longer exposes them.

## Frontend

Files are listed in the file map above. All templates named there exist.

Session model: Flask `session["user"]`; `before_request` sets `engine.state.current_user`;
`after_request` clears it; the app runs single-threaded (`threaded=False`) to avoid races.

Design: Campus Amber. Light mode is warm beige `#C4B3A5` to `#B8A392` with amber
accent `#945F04` and cream text on accent `#FFF6DC`. Dark mode is near-black brown
`#18130F` to warm glow `#2A1C12` with amber accent `#E7A743` and dark brown text on
accent `#220600`. Cards, chips, date tiles and active menu items use the measured
surface colours from the supplied scheme PDF. A faint sun-and-leaf watermark sits behind
the main feed. Space Grotesk + Inter, lucide icons via CDN, GSAP + ScrollTrigger via CDN.
The toggle is persisted in `localStorage["kizuna-theme"]` and applied before CSS loads.

Effects: spotlight hover, reveal and stagger on load, ScrollTrigger scroll reveals,
magnetic buttons, tilt cards, count-up stats, toasts, app rail, search shortcut,
composer autosize, media lightbox with download and close-X, AJAX post actions.
All motion has CSS-only reduced-motion fallbacks.

Pages: landing, auth, feed (explore, connections, trending), network, search, profile,
settings, saved, notifications, events, event detail, calendar, messages, communities,
community detail, admin, error.

## Tests

- `tests/test_core.py`: 17 tests covering accounts/roles/trie, graph/degree/chain/suggestions,
  feeds, trending, saved, comments, reports/moderation, events/catalog/pitches/RSVP, communities,
  SQLite reload.
- `tests/test_web.py`: 12 tests covering auth and sessions, posts/likes/comments, connections,
  search, profile and settings, events and RSVP, communities and private group approval,
  admin permissions, and 404 handling.
- Smoke: signup to connect to post to feeds to search to save to event to RSVP to private join to
  reload survives.
- Redesign smoke: theme bootstrap, all main pages, post media upload, AJAX like/save/comment/
  comment-delete, comments partial, avatar upload, event media upload + lightbox, calendar event,
  DM send/thread/list, and graph gating were all exercised with a temp SQLite DB and passed.

## What is left

1. Write the report from the standard template. Do not paste code.
2. Check `DS_Feature_Log.pdf` against the final feature set.
3. Prepare the viva explanation for each structure: what it is, why it was chosen, its cost.
4. Add the GitHub link to the report and confirm the submission format.
5. Optional polish only. Do not add features; the working build is the deliverable.

## Known decisions / gotchas

- Comments are fully implemented in core and web, including replies. Every comment has a
  three-dot menu; deleting a comment also removes its descendant replies.
- Post and community composers allow media-only posts; core rejects empty text with no media.
- DMs only work between accepted connections; the engine enforces this, not just the template.
- Theme choice lives in browser `localStorage`, not SQLite, so it follows the browser/profile.
- Lightbox opens catalog and post media, supports download, and closes via X, overlay, or Escape.
- Graph tools are admin-only; normal users still get Jaccard-ranked suggestions, which is not
  the BFS measurement tool.
- Spec says AI is allowed only for the UI; the backend used AI assistance too. Viva risk.
  Be able to explain each structure and trade-off without notes.
- `db` is a module-level SQLite connection; tests use `db.set_db_path(temp)`.
- Username changes must update every structure; handled in `core/auth.change_username`,
  including new post media uploaders and DM sender/receiver fields.
- Post deletion keeps report rows (moderation history) and removes likes, comments, saved
  entries, and post media rows.
- Trending window: last 7 days, score `(likes + 2*comments) / (age_days + 1)`.
- Clubs are admin-created with open joining; private groups need owner/organiser approval.
- Uploads are capped at 32 MB and limited to common image and video extensions.
- Code intentionally has no comments by project rule.
