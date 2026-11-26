# CU-connect

CU-connect is a social network for the DSA mini project at Chanakya University (B.Tech CS&AI).
It ships two interfaces over one engine: a Flask web app and a console harness.

Repository: https://github.com/vaibavl/CU-Kizuna

The point of the project is the data structures, not the framework. Every graph, trie,
heap, and feed operation runs in Python on in-memory structures. SQLite only stores rows
and is read back into memory at startup.

## Features and data structures

| Feature | What it does | Structure / algorithm |
|---|---|---|
| Accounts | Signup, login, logout, salted password hashing, profile | `dict` of users, PBKDF2 with per-user salt |
| User search | Prefix search over usernames and name words | Trie, then DFS to collect matches |
| Connections | Send, accept, reject, cancel, remove | Adjacency `dict[str, set[str]]`, plus `pending_out` / `pending_in` dicts |
| Mutual connections | Common neighbours of two users | Set intersection |
| Degree and shortest chain | Hops to another user, path up to 3 edges | BFS with a queue and parent dict |
| People you may know | Rank second-degree candidates | BFS to depth 2, score by Jaccard similarity |
| Posts and feeds | Create, delete, explore, connections feed | Post dict, per-user time-ordered lists, one global list |
| Connections feed | Merge posts from every connection, newest first | K-way merge with `heapq` (min-heap of negative timestamps) |
| Trending | Top posts among connections in the last 7 days | `heapq.nlargest` over `(likes + 2 * comments) / (age_days + 1)` |
| Likes and saved posts | Toggle like, bookmark a post | Sets per post, per-user saved dict |
| Comments | Threaded comments and replies | Tree stored by parent id, displayed by DFS |
| Notifications | Alerts with unread count | `deque` per user plus unread counter |
| Events | Calendar by date, upcoming events | Date-keyed dict plus min-heap by date |
| Event catalog | Image and video uploads with uploader name | List per event; files on disk, path in SQLite |
| Event pitches | Propose, approve, reject | `deque` of pitches with status |
| RSVP | Join, cancel, attendee count | `rsvps[event_id]` and `user_rsvps[username]` sets |
| Clubs and groups | Open clubs, public groups, private groups | Community dict, membership sets, per-community post lists |
| Moderation | Report a post, admin queue | Report `deque` plus a set of `(post_id, reporter)` |
| Persistence | Data survives restart | SQLite rows, `storage/loader.py` rebuilds every structure |

Roles are `student`, `organiser`, and `admin`. Role checks live in the engine, not only in
templates. Only admins can change roles, and the last admin cannot be demoted.

## Tech stack

- Python 3.13
- Flask 3.1 (Jinja templates, server-rendered pages)
- SQLite via the Python standard library
- Pure Python core for all DSA logic
- Vanilla JavaScript, CSS, GSAP + ScrollTrigger and lucide icons via CDN
- Space Grotesk and Inter from Google Fonts
- Campus Amber light/dark theme with reduced-motion fallbacks

## Setup

```powershell
cd "DSA sem-3 Project"
python -m venv .venv
.venv\Scripts\activate
pip install flask
```

Or install from the requirements file:

```powershell
pip install -r requirements.txt
```

## Run

Seed demo data once (optional, idempotent):

```powershell
python seed_demo.py
```

Start the web app:

```powershell
python run_web.py
```

Open http://127.0.0.1:5000.

Run the console harness instead:

```powershell
python main.py
```

## Demo credentials

All demo accounts use the password `campus123`. The admin account is separate.

| Username | Name | Role |
|---|---|---|
| `ananya` | Ananya Rao | student |
| `riya` | Riya Nair | organiser |
| `kabir` | Kabir Shah | student |
| `meera` | Meera Iyer | organiser |
| `arjun` | Arjun Menon | student |
| `zoya` | Zoya Khan | student |
| `pranav` | Pranav Desai | student |
| `admin` | CU-connect Admin | admin |

Admin password: `admin123`.

`seed_demo.py` exits without changes if the demo users already exist.

## Tests

```powershell
python -m unittest tests.test_core -v
python -m unittest tests.test_web -v
```

- Core: 17 tests. Accounts and roles, trie search, graph and BFS, feeds, trending, saved,
  comments, reports, events and RSVP, communities, SQLite reload.
- Web: 12 tests. Auth, sessions, posts and likes, comments, connections, search, profile,
  settings, events, communities, private group approval, admin permissions, 404 handling.

## Project structure

```text
config.py                 paths, admin seed, page size and limits
core/
  models.py               dataclasses for all records
  state.py                one State object holding every structure
  search.py               trie and prefix search
  auth.py                 hashing, signup/login, roles, settings
  graph.py                adjacency, pending requests, BFS, Jaccard
  notifications.py        notification queues
  posts.py                posts, feeds, comments, likes, trending, reports
  events.py               calendar, catalog, pitches, RSVP
  communities.py          clubs and groups
  engine.py               single facade used by every interface
storage/
  db.py                   SQLite schema and row helpers
  loader.py               rebuild in-memory state from SQLite
web/
  app.py                  Flask routes
  templates/              all pages and partials
  static/css/app.css      design system
  static/js/app.js        interactions and animation
tests/
  test_core.py            17 core tests
  test_web.py             12 web tests
main.py                   console harness
run_web.py                starts the Flask app
seed_demo.py              demo data and accounts
PROJECT_SPEC.md           original project spec
PROGRESS.md               feature checklist
PROGRESS.json             progress data for the TUI sidebar
HANDOFF.md                resume notes
uploads/                  uploaded event media (created at runtime)
campus.db                 SQLite database (created at runtime)
```

## Storage note

SQLite is storage only. It holds users, edges, posts, events, membership, and similar rows.
No graph traversal, feed ranking, or prefix search is done in SQL. `storage/loader.py`
rebuilds the adjacency sets, pending dicts, trie, heaps, and post lists when the app starts,
so the DSA logic always runs on Python data structures in memory.
