import calendar as calendar_module
import datetime as datetime_module
import os
import secrets
import time
import uuid
from functools import wraps
from urllib.parse import urlparse

import config
from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from io import BytesIO
from werkzeug.utils import secure_filename

from core.engine import Engine
from storage import db
from storage.blob_sync import blob_sync

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "mov"}


def engine():
    if "engine" not in g:
        g.engine = Engine(current_app.config["DB_PATH"])
    return g.engine


def load_secret():
    secret = os.environ.get("CAMPUS_SECRET")
    if secret:
        return secret
    if os.environ.get("VERCEL"):
        # Stable across serverless instances when no secret is configured.
        return "cu-kizuna-demo-secret"
    path = os.path.join(config.DATA_DIR, ".campus_secret")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            stored = handle.read().strip()
        if stored:
            return stored
    secret = secrets.token_hex(32)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(secret)
    return secret


def safe_next(target, fallback=None):
    if not target:
        return fallback
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return fallback
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return fallback
    return target


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        if not engine().is_admin(session["user"]):
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def handle(result):
    if isinstance(result, tuple):
        ok = bool(result[0])
        message = result[1] if len(result) > 1 else ""
    else:
        ok = True
        message = str(result)
    flash(message, "ok" if ok else "err")
    return ok


def back(fallback="feed"):
    target = request.form.get("next") or request.args.get("next")
    return redirect(safe_next(target, url_for(fallback)))


def wants_json():
    return request.headers.get("X-Requested-With") == "fetch"


def action_result(result, **extra):
    ok = bool(result[0])
    message = result[1] if len(result) > 1 else ""
    if wants_json():
        payload = {"ok": ok, "message": message}
        payload.update(extra)
        return jsonify(payload)
    flash(message, "ok" if ok else "err")
    return back()


def save_upload(file):
    if file is None or not file.filename:
        return None, "Choose a file first."
    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        return None, "Unsupported file type."
    filename = f"{uuid.uuid4().hex}-{secure_filename(file.filename)}"
    db.save_blob(filename, file.read(), file.mimetype or "application/octet-stream")
    return filename, None


def upload_paths(field):
    paths = []
    for file in request.files.getlist(field):
        if file is None or not file.filename:
            continue
        filename, error = save_upload(file)
        if error:
            return None, error
        paths.append(f"/uploads/{filename}")
    return paths, None


def visible_post(post):
    if post.community_id is None:
        return True
    return engine().can_read_community(post.community_id)


def relationship(username):
    e = engine()
    viewer = session.get("user")
    if viewer is None:
        return "anon"
    if username == viewer:
        return "self"
    if username in e.connections():
        return "connected"
    incoming, outgoing = e.pending_requests()
    if username in {name for name, _ in incoming}:
        return "incoming"
    if username in {name for name, _ in outgoing}:
        return "outgoing"
    return "none"


def decorate_post(post):
    e = engine()
    return {
        "post": post,
        "author": e.get_user(post.author),
        "likes": e.like_count(post.post_id),
        "liked": e.is_liked(post.post_id),
        "saved": e.is_saved(post.post_id),
        "comments": e.comment_tree(post.post_id),
        "comment_count": e.comment_count(post.post_id),
    }


def create_app(db_path=None, testing=False):
    app = Flask(__name__)
    app.secret_key = load_secret()
    app.config["UPLOAD_FOLDER"] = config.UPLOAD_DIR
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
    app.config["TESTING"] = testing
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)

    resolved_db_path = db_path or config.DB_PATH
    app.config["DB_PATH"] = resolved_db_path
    app.config["ENGINE"] = Engine(resolved_db_path)

    @app.before_request
    def prepare_request():
        g.sync_blob = not request.path.startswith("/static/")
        if g.sync_blob:
            if blob_sync.download():
                db.refresh_connection()
            db.checkpoint()
            g.db_hash = blob_sync.local_hash()
        username = session.get("user")
        if username and engine().get_user(username) is None:
            session.clear()
            username = None
        engine().state.current_user = username

    @app.after_request
    def finish_request(response):
        if "engine" in g:
            g.engine.state.current_user = None
        if g.get("sync_blob"):
            db.checkpoint()
            if blob_sync.local_hash() != g.get("db_hash"):
                blob_sync.upload()
        return response

    @app.context_processor
    def inject_layout():
        e = engine()
        username = session.get("user")
        user = e.get_user(username) if username else None
        base = {
            "me": None,
            "me_user": None,
            "unread_count": 0,
            "unread_messages": 0,
            "pending_count": 0,
            "sidebar_people": [],
            "sidebar_events": [],
            "stats": e.stats(),
            "here": request.full_path.rstrip("?"),
        }
        if user is None:
            return base
        people = []
        suggestions = e.people_you_may_know(4)
        if isinstance(suggestions, list):
            for name, score in suggestions:
                person = e.get_user(name)
                if person is not None:
                    people.append({"user": person, "score": score})
        incoming, _ = e.pending_requests()
        base.update(
            {
                "me": username,
                "me_user": user,
                "unread_count": e.unread_count(),
                "unread_messages": e.unread_message_count(),
                "pending_count": len(incoming),
                "sidebar_people": people,
                "sidebar_events": e.upcoming_events(3),
            }
        )
        return base

    @app.template_filter("timeago")
    def timeago(value):
        seconds = max(0, int(time.time() - value))
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        if seconds < 604800:
            return f"{seconds // 86400}d ago"
        return time.strftime("%d %b", time.localtime(value))

    @app.template_filter("initials")
    def initials(name):
        parts = [part for part in str(name).split() if part]
        if not parts:
            return "?"
        return "".join(part[0].upper() for part in parts[:2])

    @app.get("/")
    def index():
        if session.get("user"):
            return redirect(url_for("feed"))
        return render_template("landing.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            ok, message = engine().login(username, password)
            if ok:
                session["user"] = username.strip().lower()
                nxt = request.args.get("next")
                return redirect(safe_next(nxt, url_for("feed")))
            flash(message, "err")
        return render_template("auth.html", mode="login")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            username = request.form.get("username", "")
            name = request.form.get("name", "")
            password = request.form.get("password", "")
            ok, message = engine().signup(username, name, password)
            if ok:
                engine().login(username, password)
                session["user"] = username.strip().lower()
                flash("Welcome to CU-Kizuna.", "ok")
                return redirect(url_for("feed"))
            flash(message, "err")
        return render_template("auth.html", mode="signup")

    @app.post("/logout")
    def logout():
        engine().logout()
        session.clear()
        return redirect(url_for("index"))

    @app.get("/feed")
    @login_required
    def feed():
        tab = request.args.get("tab", "explore")
        try:
            page = int(request.args.get("page", 0))
        except (TypeError, ValueError):
            page = 0
        e = engine()
        scores = {}
        has_more = False
        if tab == "connections":
            raw = e.connections_feed(page)
            peek = e.connections_feed(page + 1) if isinstance(raw, list) and len(raw) == config.PAGE_SIZE else []
            has_more = bool(peek) and not isinstance(peek, tuple)
        elif tab == "trending":
            ranked = e.trending_posts(10)
            raw = [post for post, _ in ranked] if isinstance(ranked, list) else []
            scores = {post.post_id: score for post, score in ranked} if isinstance(ranked, list) else {}
        else:
            tab = "explore"
            raw = e.explore_feed(page)
            peek = e.explore_feed(page + 1) if isinstance(raw, list) and len(raw) == config.PAGE_SIZE else []
            has_more = bool(peek) and not isinstance(peek, tuple)
        if isinstance(raw, tuple):
            raw = []
        raw = [post for post in raw if visible_post(post)]
        items = [decorate_post(post) for post in raw]
        return render_template(
            "feed.html",
            tab=tab,
            items=items,
            page=page,
            scores=scores,
            has_more=has_more,
        )

    @app.post("/posts")
    @login_required
    def create_post():
        paths, error = upload_paths("media")
        if error:
            flash(error, "err")
            return back()
        handle(engine().create_post(request.form.get("text", ""), media_paths=paths))
        return back()

    @app.post("/posts/<int:post_id>/delete")
    @login_required
    def delete_post(post_id):
        handle(engine().delete_post(post_id))
        return back()

    @app.post("/posts/<int:post_id>/like")
    @login_required
    def like_post(post_id):
        result = engine().like_post(post_id)
        return action_result(result, liked=engine().is_liked(post_id), likes=engine().like_count(post_id))

    @app.post("/posts/<int:post_id>/unlike")
    @login_required
    def unlike_post(post_id):
        result = engine().unlike_post(post_id)
        return action_result(result, liked=False, likes=engine().like_count(post_id))

    @app.post("/posts/<int:post_id>/comment")
    @login_required
    def comment_post(post_id):
        raw_parent = request.form.get("parent_id") or None
        try:
            parent = int(raw_parent) if raw_parent else None
        except (TypeError, ValueError):
            parent = None
        result = engine().add_comment(post_id, request.form.get("text", ""), parent)
        return action_result(result, comment_count=engine().comment_count(post_id))

    @app.get("/posts/<int:post_id>/comments")
    @login_required
    def post_comments(post_id):
        post = engine().get_post(post_id)
        if post is None:
            abort(404)
        if not visible_post(post):
            abort(403)
        return render_template(
            "_comments_fragment.html",
            nodes=engine().comment_tree(post_id),
            post=post,
        )

    @app.post("/posts/<int:post_id>/comments/<int:comment_id>/delete")
    @login_required
    def delete_comment(post_id, comment_id):
        result = engine().delete_comment(post_id, comment_id)
        return action_result(result, comment_count=engine().comment_count(post_id))

    @app.post("/posts/<int:post_id>/save")
    @login_required
    def save_post(post_id):
        result = engine().save_post(post_id)
        return action_result(result, saved=engine().is_saved(post_id))

    @app.post("/posts/<int:post_id>/unsave")
    @login_required
    def unsave_post(post_id):
        result = engine().unsave_post(post_id)
        return action_result(result, saved=False)

    @app.post("/posts/<int:post_id>/report")
    @login_required
    def report_post(post_id):
        result = engine().report_post(post_id, request.form.get("reason", ""))
        return action_result(result)

    @app.get("/network")
    @login_required
    def network():
        e = engine()
        incoming, outgoing = e.pending_requests()
        conns = [e.get_user(name) for name in e.connections()]
        suggestions = []
        for name, score in e.people_you_may_know(12):
            person = e.get_user(name)
            if person is not None:
                suggestions.append({"user": person, "score": score})
        return render_template(
            "network.html",
            incoming=incoming,
            outgoing=outgoing,
            connections=[person for person in conns if person is not None],
            suggestions=suggestions,
        )

    @app.post("/network/request/<username>")
    @login_required
    def send_request(username):
        handle(engine().send_request(username))
        return back("network")

    @app.post("/network/accept/<username>")
    @login_required
    def accept_request(username):
        handle(engine().accept_request(username))
        return back("network")

    @app.post("/network/reject/<username>")
    @login_required
    def reject_request(username):
        handle(engine().reject_request(username))
        return back("network")

    @app.post("/network/cancel/<username>")
    @login_required
    def cancel_request(username):
        handle(engine().cancel_request(username))
        return back("network")

    @app.post("/network/remove/<username>")
    @login_required
    def remove_connection(username):
        handle(engine().remove_connection(username))
        return back("network")

    @app.get("/search")
    @login_required
    def search():
        query = request.args.get("q", "").strip()
        results = []
        if query:
            for name in engine().search_users(query, 20):
                person = engine().get_user(name)
                if person is not None:
                    results.append({"user": person, "rel": relationship(person.username)})
        return render_template("search.html", query=query, results=results)

    @app.get("/u/<username>")
    @login_required
    def profile(username):
        e = engine()
        user = e.get_user(username)
        if user is None:
            abort(404)
        items = [decorate_post(post) for post in e.posts_by(username) if visible_post(post)]
        is_self = username == session.get("user")
        mutual = [] if is_self else e.mutual_connections(username)
        return render_template(
            "profile.html",
            user=user,
            items=items,
            is_self=is_self,
            rel=relationship(username),
            mutual=mutual,
            degree=e.connection_degree(username),
            connection_count=len(e.connections(username)),
        )

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        if request.method == "POST":
            kind = request.form.get("kind")
            if kind == "profile":
                handle(engine().update_profile(request.form.get("name") or None, request.form.get("bio", "")))
            elif kind == "password":
                handle(engine().change_password(request.form.get("old_password", ""), request.form.get("new_password", "")))
            elif kind == "username":
                new_name = request.form.get("new_username", "")
                if handle(engine().change_username(new_name)):
                    session["user"] = new_name.strip().lower()
            return back("settings")
        return render_template("settings.html")

    @app.post("/settings/avatar")
    @login_required
    def upload_avatar():
        filename, error = save_upload(request.files.get("avatar"))
        if error:
            flash(error, "err")
            return back("settings")
        handle(engine().update_avatar(filename))
        return back("settings")

    @app.get("/saved")
    @login_required
    def saved():
        items = [decorate_post(post) for post in engine().saved_posts() if visible_post(post)]
        return render_template("saved.html", items=items)

    @app.get("/notifications")
    @login_required
    def notifications():
        unread_only = request.args.get("unread") == "1"
        notes = engine().notifications(unread_only)
        return render_template("notifications.html", notes=notes if isinstance(notes, list) else [], unread_only=unread_only)

    @app.post("/notifications/read")
    @login_required
    def mark_read():
        raw_note = request.form.get("notification_id") or None
        try:
            note_id = int(raw_note) if raw_note else None
        except (TypeError, ValueError):
            note_id = None
        handle(engine().mark_notifications_read(note_id))
        return back("notifications")

    @app.get("/events")
    @login_required
    def events():
        e = engine()
        date = request.args.get("date") or None
        items = e.events_on(date) if date else e.upcoming_events(50)
        pitches = e.pitches()
        return render_template(
            "events.html",
            items=items,
            date=date,
            pitches=pitches[2] if isinstance(pitches, tuple) and pitches[0] else [],
        )

    @app.get("/calendar")
    @login_required
    def calendar():
        today = datetime_module.date.today()
        try:
            year = int(request.args.get("year", today.year))
            month = int(request.args.get("month", today.month))
        except (TypeError, ValueError):
            year, month = today.year, today.month
        if year < 1 or year > 9999 or month < 1 or month > 12:
            year, month = today.year, today.month
        try:
            selected_day = int(request.args.get("day")) if request.args.get("day") else None
        except (TypeError, ValueError):
            selected_day = None
        if selected_day is not None:
            try:
                datetime_module.date(year, month, selected_day)
            except ValueError:
                selected_day = None
        prefix = f"{year:04d}-{month:02d}-"
        by_day = {}
        for event in engine().all_events():
            if event.date.startswith(prefix):
                try:
                    day = int(event.date[8:10])
                except (TypeError, ValueError):
                    continue
                by_day.setdefault(day, []).append(event)
        weeks = calendar_module.Calendar(firstweekday=0).monthdayscalendar(year, month)
        return render_template(
            "calendar.html",
            year=year,
            month=month,
            month_name=calendar_module.month_name[month],
            weeks=weeks,
            weekdays=calendar_module.day_name,
            by_day=by_day,
            selected_day=selected_day,
            selected_events=by_day.get(selected_day, []) if selected_day else [],
            previous_month=(year - 1, 12) if month == 1 else (year, month - 1),
            next_month=(year + 1, 1) if month == 12 else (year, month + 1),
            today=today,
        )

    @app.post("/events/add")
    @login_required
    def add_event():
        handle(
            engine().add_event(
                request.form.get("title", ""),
                request.form.get("description", ""),
                request.form.get("date", ""),
                request.form.get("time", ""),
                request.form.get("venue", ""),
            )
        )
        return back("events")

    @app.get("/events/<int:event_id>")
    @login_required
    def event_detail(event_id):
        e = engine()
        event = e.get_event(event_id)
        if event is None:
            abort(404)
        return render_template(
            "event_detail.html",
            event=event,
            catalog=e.catalog_for(event_id),
            attendees=sorted(e.attendees(event_id)),
            going=e.is_going(event_id),
            count=e.attendee_count(event_id),
        )

    @app.post("/events/<int:event_id>/rsvp")
    @login_required
    def rsvp(event_id):
        handle(engine().rsvp(event_id))
        return back("events")

    @app.post("/events/<int:event_id>/cancel-rsvp")
    @login_required
    def cancel_rsvp(event_id):
        handle(engine().cancel_rsvp(event_id))
        return back("events")

    @app.post("/events/<int:event_id>/upload")
    @login_required
    def upload_media(event_id):
        file = request.files.get("file")
        if file is None or not file.filename:
            flash("Choose a file first.", "err")
            return back("events")
        extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if extension not in ALLOWED_EXTENSIONS:
            flash("Unsupported file type.", "err")
            return back("events")
        filename = f"{uuid.uuid4().hex}-{secure_filename(file.filename)}"
        db.save_blob(filename, file.read(), file.mimetype or "application/octet-stream")
        handle(engine().upload_media(event_id, f"/uploads/{filename}"))
        return redirect(url_for("event_detail", event_id=event_id))

    @app.get("/messages")
    @login_required
    def messages():
        result = engine().conversations()
        threads = result[2] if isinstance(result, tuple) and result[0] else []
        people = [engine().get_user(name) for name in sorted(engine().connections())]
        return render_template(
            "messages.html",
            threads=threads,
            peer=None,
            thread=[],
            people=[person for person in people if person is not None],
        )

    @app.get("/messages/<username>")
    @login_required
    def conversation(username):
        user = engine().get_user(username)
        if user is None or username not in engine().connections():
            abort(403)
        engine().mark_conversation_read(username)
        result = engine().conversation(username)
        thread = result[2] if isinstance(result, tuple) and result[0] else []
        threads_result = engine().conversations()
        threads = threads_result[2] if isinstance(threads_result, tuple) and threads_result[0] else []
        people = [engine().get_user(name) for name in sorted(engine().connections())]
        return render_template(
            "messages.html",
            threads=threads,
            peer=user,
            thread=thread,
            people=[person for person in people if person is not None],
        )

    @app.post("/messages/<username>/send")
    @login_required
    def send_message(username):
        result = engine().send_message(username, request.form.get("text", ""))
        if wants_json():
            return action_result(result)
        if result[0]:
            flash(result[1], "ok")
        else:
            flash(result[1], "err")
        return redirect(url_for("conversation", username=username))

    @app.post("/events/pitch")
    @login_required
    def propose_pitch():
        handle(engine().propose_pitch(request.form.get("title", ""), request.form.get("description", "")))
        return back("events")

    @app.post("/events/pitch/<int:pitch_id>/review")
    @login_required
    def review_pitch(pitch_id):
        handle(engine().review_pitch(pitch_id, request.form.get("action", "")))
        return back("admin")

    @app.get("/communities")
    @login_required
    def communities():
        return render_template("communities.html", items=engine().list_communities())

    @app.post("/communities/create")
    @login_required
    def create_community():
        kind = request.form.get("kind", "group")
        name = request.form.get("name", "")
        if kind == "club":
            handle(engine().create_club(name))
        else:
            handle(engine().create_group(name, request.form.get("visibility", "public")))
        return back("communities")

    @app.get("/communities/<int:community_id>")
    @login_required
    def community_detail(community_id):
        e = engine()
        community = e.get_community(community_id)
        if community is None:
            abort(404)
        role = e.community_role(community_id)
        feed_error = None
        items = []
        result = e.community_feed(community_id, 0)
        if isinstance(result, tuple):
            if result[0]:
                items = [decorate_post(post) for post in result[2]]
            else:
                feed_error = result[1]
        pending = e.community_pending(community_id) if role in ("owner", "organiser") or e.is_admin() else []
        readable = e.can_read_community(community_id) or e.is_admin()
        members = e.community_members(community_id) if readable else []
        organisers = e.state.community_organisers.get(community_id, set()) if readable else set()
        return render_template(
            "community_detail.html",
            community=community,
            role=role,
            items=items,
            feed_error=feed_error,
            readable=readable,
            members=members,
            organisers=organisers,
            pending=pending,
        )

    @app.post("/communities/<int:community_id>/join")
    @login_required
    def join_community(community_id):
        handle(engine().join_community(community_id))
        return redirect(url_for("community_detail", community_id=community_id))

    @app.post("/communities/<int:community_id>/leave")
    @login_required
    def leave_community(community_id):
        handle(engine().leave_community(community_id))
        return redirect(url_for("community_detail", community_id=community_id))

    @app.post("/communities/<int:community_id>/post")
    @login_required
    def post_community(community_id):
        paths, error = upload_paths("media")
        if error:
            flash(error, "err")
            return redirect(url_for("community_detail", community_id=community_id))
        handle(engine().post_to_community(community_id, request.form.get("text", ""), paths))
        return redirect(url_for("community_detail", community_id=community_id))

    @app.post("/communities/<int:community_id>/approve/<username>")
    @login_required
    def approve_join(community_id, username):
        handle(engine().approve_join(community_id, username))
        return redirect(url_for("community_detail", community_id=community_id))

    @app.post("/communities/<int:community_id>/reject/<username>")
    @login_required
    def reject_join(community_id, username):
        handle(engine().reject_join(community_id, username))
        return redirect(url_for("community_detail", community_id=community_id))

    @app.post("/communities/<int:community_id>/organiser")
    @login_required
    def assign_organiser(community_id):
        handle(engine().assign_organiser(community_id, request.form.get("username", "")))
        return redirect(url_for("community_detail", community_id=community_id))

    @app.get("/admin")
    @admin_required
    def admin():
        e = engine()
        queue = e.moderation_queue()
        pitches = e.pitches()
        reports = queue[2] if isinstance(queue, tuple) and queue[0] else []
        rows = []
        for report in reports:
            rows.append({"report": report, "post": e.get_post(report.post_id)})
        target = request.args.get("target", "").strip()
        tool = None
        if target:
            person = e.get_user(target)
            if person is not None:
                tool = {
                    "user": person,
                    "degree": e.connection_degree(target),
                    "chain": e.shortest_chain(target),
                    "mutual": e.mutual_connections(target),
                }
        return render_template(
            "admin.html",
            users=e.all_users(),
            role_log=e.role_log(),
            queue=rows,
            pitches=pitches[2] if isinstance(pitches, tuple) and pitches[0] else [],
            graph_target=target,
            graph_tool=tool,
        )

    @app.post("/admin/role")
    @admin_required
    def set_role():
        handle(engine().set_role(request.form.get("username", ""), request.form.get("role", "")))
        return back("admin")

    @app.post("/admin/reports/<int:report_id>")
    @admin_required
    def review_report(report_id):
        handle(engine().review_report(report_id, request.form.get("action", "")))
        return back("admin")

    @app.get("/uploads/<path:filename>")
    def uploaded(filename):
        entry = db.get_blob(filename)
        if entry:
            return send_file(
                BytesIO(entry["data"]),
                mimetype=entry["content_type"],
                download_name=filename,
            )
        return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="You do not have permission to open this page."), 403

    @app.errorhandler(404)
    def missing(_error):
        return render_template("error.html", code=404, message="That page or record does not exist."), 404

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=False)
