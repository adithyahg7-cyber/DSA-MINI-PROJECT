# DSA Mini Project: CU-Kizuna (handoff spec)

> Purpose: a complete plan so any LLM can continue this project without the earlier chat.
> App name: not decided yet (student is free to name it).

## 0. Context and hard constraints

- Course: Data Structures and Algorithms, Chanakya University, B.Tech (CS&AI). Submission: **27-11-2026**. Marks: core engine and DSA usage 30, implementation 20, report 10, understanding and viva 40.
- Language: **Python**. Storage: **SQLite**. UI: Flask web app (console menu is the minimum the PDF accepts).
- **AI tools are allowed only for the user interface.** The student is answerable for every line. So write the **core engine simply, with comments**, and explain it in plain words. Code the student cannot explain earns no marks.
- Graph computations (suggestions, degrees, paths, feed) must run in **Python on in-memory structures**, never as SQL queries. SQLite only stores data.
- Keep the **core engine separate from the interface**, so a console or web UI calls the same functions.
- No self edges, no multiple edges. Accepted connection = undirected edge. Pending request = directed edge (sender to receiver).
- The report is short, uses the standard template, one copy per team plus a GitHub link. It must not contain pasted code.
- Teacher's preferred explanation style for the student: very simple, slow, detailed, with diagrams.

## 1. Decisions already made

1. Event catalog is **Tier 2** (images only first, videos last).
2. Persistence is **SQLite**; structures are rebuilt in memory at startup.
3. Feed has **two tabs**: Connections feed (PDF requirement, heap) and Explore feed (posts from everyone).
4. **Roles** are `student`, `organiser`, `admin`. Users cannot choose roles; **only admins set roles** (see section 4.1). No role-request feature.
5. **No suggested groups** feature.
6. **Groups** have two modes, **public** and **private**. **Clubs** are separate from groups.
7. Four extras are chosen: **trending posts**, **event RSVP**, **saved posts**, **post reporting with an admin moderation queue** (section 2, Extras). Build them only after Tier 1 and the Tier 2 core work.

## 2. Feature list

### Tier 1 (must, from the PDF)
Accounts (signup, login, logout, hashed passwords, profile) / Connections (send, accept, reject, cancel, remove, view, mutual, people you may know, degree, shortest chain) / Posts (create, view own, delete own) and feeds / Search (prefix) / Persistence / Interface.

### Tier 2 (strong)
Roles / notifications / likes and comments with replies / account settings / event calendar / event catalog (images, shows uploader) / event pitch dashboard.

### Tier 3 (if time)
Clubs (discussion feed) / groups (public or private).

### Extras (chosen, build after Tier 1 and Tier 2 core)
Trending posts among connections / event RSVP / saved posts (bookmarks) / report a post with an admin moderation queue.

### Tier 4 (last)
Video uploads in the catalog.

## 3. Data structure and algorithm log

| Feature | Structure / algorithm | Why |
|---|---|---|
| Find user, unique username | Hash table (`dict`) | O(1) lookup |
| Passwords | Salted hash (`hashlib`) | Never store plain text; same password gives different hashes |
| Network | Graph as adjacency lists (`dict` of `set`) | Sets give O(1) add, remove, check |
| Pending requests | Directed graph in two dicts: `pending_out[sender]` and `pending_in[receiver]`, each `{other: timestamp}` | O(1) unlink on reject or cancel; insertion order keeps oldest first |
| Mutual connections | Set intersection `adj[a] & adj[b]` | Common neighbours |
| Degree of connection and shortest chain | BFS with `parent` dict, depth limit 3 | BFS finds shortest path when edges are equal |
| People you may know | BFS to depth 2, rank by Jaccard (mutual / union of neighbours) | Only friends of friends are candidates |
| Posts lookup | Hash table `posts[id]` plus `user_posts[username]` (time-ordered list) | O(1) find; lists are already sorted |
| Connections feed | Max-heap merge of the connections' sorted post lists (`heapq` with negative timestamps) | Merge k sorted lists without sorting everything |
| Explore feed | One global time-ordered list `all_posts`, read from the end | One stream, so no heap needed |
| User search | Trie (prefix search); insert username and each word of the name, lowercase | Cost depends on prefix length and result count |
| Persistence | SQLite; rebuild adjacency, pending dicts, trie, post dicts at startup | Graph logic stays in Python |
| Roles | `role` field; permission check in the engine; admin-only `set_role` | O(1) check |
| Role log | Append-only list of (who, whose, old role, new role, time) | Accountability |
| Notifications | Queue (`deque`) per user plus unread counter | FIFO, newest or oldest view |
| Likes | `set` of usernames per post | No duplicates, O(1) |
| Comments and replies | Tree; display by DFS | Replies nest naturally |
| Account settings | Edit fields; password change re-salts and re-hashes; username change updates dict and trie | No special structure |
| Event calendar | `dict` keyed by date holding event lists, plus a min-heap by date for upcoming events | O(1) per day, fast "next event" |
| Event catalog | `catalog[event_id]` list of media items `{path, uploader, time}`; files on disk, only the path in the DB | Shows who uploaded |
| Pitch dashboard | Queue of pitches with status `pending`, `approved`, `rejected` | Oldest reviewed first |
| Trending posts | Score each recent post of connections, take the top k with a heap (`heapq.nlargest`) | Top k without sorting all posts |
| Event RSVP | `rsvps[event_id]` set of usernames, plus `user_rsvps[username]` set of event IDs | O(1) join, leave, check; count = size of set |
| Saved posts | `saved[username]` dict `{post_id: time_saved}` | O(1) save and unsave; insertion order gives most recent last |
| Post reports | Queue (`deque`) of report records with status, plus a set of `(post_id, reporter)` | FIFO review; the set blocks duplicate reports |
| Clubs and groups | `communities[id]` with `members` set, `organisers` or `owner`, and `posts` list; `user_communities[username]` set | O(1) membership check; feed read from the end |

## 4. Feature design notes

### 4.1 Roles (admin only)
- Signup always creates `student`. The signup code ignores any role input.
- `set_role(acting_user, target, new_role)`: refuse unless `acting_user.role == "admin"`. The check is **inside the engine**, not only in the UI.
- First admin: the app **seeds one admin account on first start** (credentials from a config file).
- **Safety rule:** refuse to demote the **last remaining admin**.
- **Role log:** every change is recorded (who, whose, old, new, time) and saved in SQLite.
- Optional later: tie organisers to a specific club (a club keeps a set of organisers) so an organiser cannot post events for another club.

### 4.2 Connections
- Send: refuse if self, already connected, or a pending request exists in either direction.
- Accept: delete from both pending dicts, add both directions in `adj`.
- Reject / cancel: delete from both pending dicts only.
- Remove connection: delete both directions in `adj`.
- Notify the receiver when a request is sent, and the sender when it is accepted.

### 4.3 Feeds
- Connections feed: push each connection's newest post into a heap, pop the newest, push that person's next post. Return pages of 10 ("load more").
- Explore feed: read `all_posts` from the end in pages of 10.
- Deleting a post removes it from `posts`, `user_posts`, `all_posts`, and any community list.

### 4.3.1 Search
- Walk the trie along the typed letters, then DFS from that node to collect suggestions (cap 5 to 10).

### 4.4 Event system
- Only `organiser` or `admin` can add events or upload to the catalog (role check in the engine).
- Approved pitch: admin approves, the student is notified, the pitch can be turned into a calendar event.

### 4.4.1 Event RSVP
- Any logged-in user can RSVP to an existing event: add the username to `rsvps[event_id]` and the event ID to `user_rsvps[username]`. Cancel removes both.
- The calendar shows the attendee count (`len` of the set) and whether the current user is going.
- Optional: notify the organiser on the first RSVPs. Keep it off by default to avoid noise.

### 4.4.2 Trending posts
- Only posts from the user's connections, from the last 7 days.
- Score = `(likes + 2 * comments) / (age_in_days + 1)`. More activity raises it, age lowers it.
- Take the top 10 using `heapq.nlargest(10, candidates, key=score)`. Cost is O(n log k) for n candidate posts.
- Shown as a third tab or a side panel ("Trending among your connections").

### 4.4.3 Saved posts
- Save and unsave toggle the post in `saved[username]`.
- The saved page shows the most recently saved first (read the dict in reverse).
- If a saved post was deleted, skip it when listing (and remove it from the dict).

### 4.4.4 Reporting and moderation
- Any user can report a post (not their own) with a short reason. Reject a second report of the same post by the same user (check the set).
- Each report goes into the moderation queue with status `pending`.
- **Admins only** can review (role check in the engine), oldest first. Two actions: **dismiss** (status `dismissed`) or **remove post** (call the normal delete-post function, status `actioned`, and notify the author).
- Every decision records who decided and when, and is saved in SQLite.

### 4.5 Communities
- **Clubs:** created by an admin, who assigns organisers. Organisers manage the club; members read and post in its discussion feed.
- **Groups:** created by any student (creator is the owner). Mode **public**: anyone can join and read. Mode **private**: joining needs the owner's approval (reuse the pending-dict idea) and only members can read posts.
- Both use the same `Community` structure with a `type` field (`club` or `group`) and a `visibility` field.

## 5. Architecture

```
project/
  main.py                 # starts the app (loads data, then runs the UI)
  config.py               # admin seed credentials, upload folder, limits
  core/                   # PURE PYTHON, no UI code, no graph logic in SQL
    models.py             # User, Post, Comment, Event, Pitch, Community
    auth.py               # users dict, salted hashing, login state, roles, set_role, role log
    graph.py              # adj sets, pending dicts, BFS, mutual, Jaccard
    search.py             # Trie
    posts.py              # posts, user_posts, all_posts, heap feed, likes, comment tree, trending, saved posts, reports
    notifications.py      # deque per user
    events.py             # calendar, catalog, pitches, RSVPs
    communities.py        # clubs and groups
    engine.py             # ONE facade class: the only thing the UI calls
  storage/
    db.py                 # SQLite schema and save/delete functions (no logic)
    loader.py             # at startup: read all rows, rebuild every in-memory structure
  web/                    # UI (AI help allowed here)
    app.py                # Flask routes, each calls one engine method
    templates/ static/
  uploads/                # catalog images on disk
  tests/                  # small tests for graph, feed, trie, roles
  docs/                   # this file, the data structure log PDF, the report
```

**Rules**
1. Layers only depend downward: web calls engine; engine calls core modules and storage; core modules never import web.
2. The UI never touches the structures directly, only `engine` methods. Every engine method **changes memory first, then writes to SQLite**.
3. Permission checks (roles, ownership, membership) live in the engine.
4. Notifications are created by the engine after an action (request, accept, like, comment, pitch decision), so the core modules stay independent.

### Build order (each step is testable before the next)
1. `models.py` and `storage/db.py` (tables for users, connections, pending, posts, comments, likes, notifications, events, media, pitches, communities, role log, rsvps, saved posts, reports).
2. `auth.py`: users dict, hashing, login and logout, roles, seeded admin, `set_role`, role log.
3. `graph.py`: adjacency sets, pending dicts, send/accept/reject/cancel/remove, mutual, BFS degree and chain, Jaccard suggestions.
4. `search.py`: trie.
5. `posts.py`: posts, per-user lists, global list, heap feed.
6. `storage/loader.py` and `engine.py`: wire everything, load on startup. **Test everything with a small console menu here.** Tier 1 is then complete.
7. Flask routes and templates for Tier 1 (use AI for this part).
8. Tier 2: notifications, likes and comments, settings, calendar, catalog, pitches. Then the extras: saved posts, RSVP, trending, reports.
9. Tier 3: clubs and groups.
10. Report and viva preparation: for each structure, be able to say what it is, why it was chosen, and its cost.

## 6. Viva checklist (student must be able to explain)
- Hash table vs password hashing (two different things); why salt.
- Why adjacency list of sets; undirected edge means two insertions.
- Why BFS gives the shortest chain; the role of the `parent` dict.
- Jaccard formula and why only 2nd-degree users are candidates.
- Heap feed: why negative timestamps (`heapq` is a min-heap), cost O(m log k).
- Trie vs scanning all users.
- Why feeds and graph logic are not done with SQL.
- Why role checks are in the engine and not only in the UI.
- Trending: how the score works and why a heap gives the top k cheaply.
- Why RSVPs and saved posts are sets or dicts (O(1) toggle, no duplicates).
- Why reports use a queue, and how duplicate reports are blocked.

## 7. Other ideas (not chosen)
Undo and back navigation with a stack (listed in the PDF), skill-based search with an inverted index, teammate-finding posts matched by skill overlap.
