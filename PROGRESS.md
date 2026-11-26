# CU-Kizuna Progress

Legend: `[x]` done, `[~]` in progress, `[ ]` pending

## Foundation
- [x] `config.py`: paths, seed admin, limits
- [x] `core/models.py`: User (avatar), Post (media), PostMedia, Comment, Notification, Event, Media, Message, Pitch, Community, Report
- [x] `core/state.py`: single in-memory State object (all structures)
- [x] `storage/db.py`: schema, avatar migration, media/message tables, save/delete/rename helpers

## Core modules
- [x] `core/search.py`: Trie prefix search
- [x] `core/auth.py`: salted hashing, signup/login, roles, role log, settings, avatar, rename
- [x] `core/graph.py`: adjacency, pending, BFS, mutuals, Jaccard
- [x] `core/notifications.py`: deque per user
- [x] `core/posts.py`: posts with media, feeds, likes, comments, recursive comment delete, trending, saved, reports
- [x] `core/messages.py`: DMs between connected users, conversations, unread counts
- [x] `core/events.py`: calendar data, catalog, pitches, RSVP
- [x] `core/communities.py`: clubs and groups, media posts

## Wiring
- [x] `storage/loader.py`: rebuild State from SQLite, including new records
- [x] `core/engine.py`: single facade, including DM/media/calendar methods
- [x] `main.py`: console smoke-test menu

## Verification
- [x] `tests/test_core.py`: 17 tests pass
- [x] `tests/test_web.py`: 12 tests pass
- [x] Tier 1 smoke test (signup to connect to post to feed to search)
- [x] Restart smoke test (data survives reload)
- [x] Redesign smoke test (uploads, AJAX actions, calendar, DMs, graph gating)

## Frontend
- [x] `web/app.py` + auth: routes, sessions, login, signup, logout
- [x] feed + posts: explore, connections, trending, media uploads, likes, comments, save, report
- [x] non-refreshing post actions: like, unlike, save, unsave, comment, report, comment delete
- [x] comments: three-dot menu with delete on every comment
- [x] network + profile: requests, connections, mutuals, suggestions, profile photo, DM button
- [x] graph tools: removed from Network, admin-only in Control room
- [x] events: event list, catalog view/download with close-X lightbox, pitches
- [x] calendar: separate nav tab, month grid, per-day event details
- [x] direct messages: conversation list, bubbles, unread badge, connected-users only
- [x] communities: clubs, public groups, private groups with approval
- [x] admin + alerts: roles, moderation queue, pitch review, graph tools, notifications
- [x] Campus Amber design system: warm brown/amber light + dark surfaces, watermark, persisted toggle
- [x] composer: photo/video upload chips for feed and community posts
- [x] settings: profile photo upload
- [x] responsive shell, CSS + JS effects
- [x] `seed_demo.py`: demo users, posts, events, communities, pitches

### Pages
`base`, `shell`, `landing`, `auth`, `feed`, `_post`, `_comments`, `_comments_fragment`, `network`, `search`,
`profile`, `settings`, `saved`, `notifications`, `events`, `event_detail`, `calendar`, `messages`,
`communities`, `community_detail`, `admin`, `error`.

### Effects
Spotlight hover, tilt cards, magnetic buttons, count-up stats, GSAP reveal and stagger,
ScrollTrigger scroll reveals, toasts, app rail, search shortcut, composer autosize,
persisted light/dark toggle, media lightbox with download and close-X, AJAX post actions.
All motion has reduced-motion fallbacks.

Overall: **all planned features complete; verification passing.**
