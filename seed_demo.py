import sys

from core.engine import Engine

PASSWORD = "campus123"

PEOPLE = [
    ("ananya", "Ananya Rao", "B.Tech CS&AI. Robotics, graph theory and far too much filter coffee."),
    ("riya", "Riya Nair", "Product design. I make things look like they were always meant that way."),
    ("kabir", "Kabir Shah", "Backend and databases. SQLite apologist."),
    ("meera", "Meera Iyer", "Data science, cricket analytics, and long walks across the quad."),
    ("arjun", "Arjun Menon", "Film club. Ask me for a recommendation, not a short one."),
    ("zoya", "Zoya Khan", "Music, open mics, and finding the quietest corner of the library."),
    ("pranav", "Pranav Desai", "Second year. Here for the events."),
]


def actor(engine, username):
    engine.state.current_user = username


def make_user(engine, username, name, bio):
    if engine.get_user(username) is not None:
        return False
    actor(engine, None)
    ok, message = engine.signup(username, name, PASSWORD)
    if not ok:
        raise SystemExit(f"signup {username} failed: {message}")
    actor(engine, username)
    engine.update_profile(name, bio)
    return True


def connect(engine, first, second):
    actor(engine, first)
    engine.send_request(second)
    actor(engine, second)
    engine.accept_request(first)


def post(engine, username, text, community_id=None):
    actor(engine, username)
    ok, message, entry = engine.create_post(text, community_id)
    if not ok:
        raise SystemExit(f"post by {username} failed: {message}")
    return entry.post_id


def main():
    engine = Engine()
    if engine.get_user("ananya") is not None:
        print("Demo users already exist. Nothing to do.")
        return

    created = 0
    for username, name, bio in PEOPLE:
        if make_user(engine, username, name, bio):
            created += 1
    print(f"Users created: {created}")

    actor(engine, None)
    admin_ok, admin_message = engine.login("admin", "admin123")
    if not admin_ok:
        raise SystemExit(f"admin login failed: {admin_message}")

    connect(engine, "ananya", "riya")
    connect(engine, "ananya", "kabir")
    connect(engine, "riya", "kabir")
    connect(engine, "kabir", "meera")
    connect(engine, "meera", "arjun")
    connect(engine, "ananya", "zoya")

    actor(engine, "arjun")
    engine.send_request("ananya")
    actor(engine, "zoya")
    engine.send_request("riya")
    actor(engine, "pranav")
    engine.send_request("kabir")
    print("Connections and pending requests ready.")

    posts = {}
    posts["ananya"] = post(
        engine,
        "ananya",
        "We got the line-following bot to finish the track without flipping over. Twelve hours of debugging for four seconds of glory.",
    )
    posts["riya"] = post(
        engine,
        "riya",
        "Design tip of the day: if you have to explain the button, the button is wrong.",
    )
    posts["kabir"] = post(
        engine,
        "kabir",
        "Rewrote my feed query as a heap merge instead of a sort. Same output, far fewer comparisons. The viva answer writes itself.",
    )
    posts["meera"] = post(
        engine,
        "meera",
        "Ran the attendance data through a small clustering model. Three groups emerged and one of them is basically 'people who sit near the door'.",
    )
    posts["arjun"] = post(
        engine,
        "arjun",
        "Film club screening this Friday. Bring a blanket, the projector still runs hot.",
    )
    posts["pranav"] = post(
        engine,
        "pranav",
        "Selling last semester assignment solutions, DM fast, limited stock.",
    )
    posts["zoya"] = post(
        engine,
        "zoya",
        "Open mic sign-ups are live. First-timers get the good microphone, I do not make the rules.",
    )
    print(f"Posts created: {len(posts)}")

    actor(engine, "riya")
    engine.like_post(posts["ananya"])
    actor(engine, "kabir")
    engine.like_post(posts["ananya"])
    engine.like_post(posts["meera"])
    actor(engine, "ananya")
    engine.like_post(posts["riya"])
    engine.add_comment(posts["riya"], "Saving this for the next review.")
    actor(engine, "meera")
    engine.add_comment(posts["kabir"], "This is the version I would defend in the viva.")
    actor(engine, "arjun")
    engine.add_comment(posts["kabir"], "Print the code and frame it.")
    actor(engine, "zoya")
    engine.like_post(posts["arjun"])
    engine.add_comment(posts["arjun"], "Count me in, I will bring the playlist.")
    actor(engine, "kabir")
    engine.report_post(posts["pranav"], "Spam: selling assignment solutions.")
    print("Likes, comments and one report added.")

    actor(engine, "admin")
    engine.set_role("riya", "organiser")
    engine.set_role("meera", "organiser")

    events = []
    actor(engine, "admin")
    ok, message, event = engine.add_event(
        "CU-Kizuna Hack Night",
        "One evening, small teams, any stack. Bring a laptop and an idea; we bring the pizza and the extension cords.",
        "2026-12-04",
        "18:00",
        "Innovation Lab, Block C",
    )
    if ok:
        events.append(event.event_id)
    actor(engine, "riya")
    ok, message, event = engine.add_event(
        "Design Jam: CU-Kizuna Identity",
        "A two-hour studio session redesigning the CU-Kizuna wayfinding signs. Sketches first, software later.",
        "2026-12-08",
        "16:30",
        "Design Studio, Block A",
    )
    if ok:
        events.append(event.event_id)
    actor(engine, "meera")
    ok, message, event = engine.add_event(
        "Data Clinic",
        "Bring a messy dataset and leave with a plan. Open to all years, no prior experience needed.",
        "2026-12-12",
        "15:00",
        "Seminar Hall 2",
    )
    if ok:
        events.append(event.event_id)

    for username in ("ananya", "kabir", "zoya"):
        actor(engine, username)
        if events:
            engine.rsvp(events[0])
    for username in ("ananya", "arjun"):
        actor(engine, username)
        if len(events) > 1:
            engine.rsvp(events[1])
    actor(engine, "kabir")
    if len(events) > 2:
        engine.rsvp(events[2])
    print(f"Events created: {len(events)}")

    actor(engine, "admin")
    ok, message, club = engine.create_club("Robotics Club")
    robotics = club.community_id if ok else None
    ok, message, club = engine.create_club("Design Collective")
    design = club.community_id if ok else None
    if robotics is not None:
        engine.assign_organiser(robotics, "ananya")
    if design is not None:
        engine.assign_organiser(design, "riya")

    actor(engine, "ananya")
    ok, message, group = engine.create_group("Placement Prep", "public")
    placement = group.community_id if ok else None
    actor(engine, "kabir")
    ok, message, group = engine.create_group("Startup Circle", "private")
    startup = group.community_id if ok else None

    for username in ("kabir", "meera", "zoya"):
        actor(engine, username)
        if robotics is not None:
            engine.join_community(robotics)
    for username in ("ananya", "meera"):
        actor(engine, username)
        if design is not None:
            engine.join_community(design)
    for username in ("riya", "kabir", "meera"):
        actor(engine, username)
        if placement is not None:
            engine.join_community(placement)
    actor(engine, "zoya")
    if startup is not None:
        engine.join_community(startup)
    actor(engine, "kabir")
    if startup is not None:
        engine.approve_join(startup, "zoya")

    if placement is not None:
        post(
            engine,
            "ananya",
            "Placement prep starts Sunday. We are doing two DSA problems and one mock interview each week.",
            placement,
        )
        post(
            engine,
            "riya",
            "Sharing my resume template in the group tomorrow. Keep it to one page.",
            placement,
        )
    if robotics is not None:
        post(
            engine,
            "ananya",
            "Club meeting moved to Thursday. Bring your bot, working or not.",
            robotics,
        )
    print("Communities and community posts ready.")

    actor(engine, "arjun")
    engine.propose_pitch(
        "Open Air Film Screening",
        "One classic film, one blanket-friendly lawn, and a proper sound setup. Friday after classes.",
    )
    actor(engine, "zoya")
    engine.propose_pitch(
        "Busking Friday",
        "A small acoustic set outside the cafe every other Friday. Students rotate as performers.",
    )
    actor(engine, "admin")
    ok, message, pitches = engine.pitches()
    if ok:
        for pitch in pitches:
            if pitch.proposer == "arjun":
                engine.review_pitch(pitch.pitch_id, "approve")
    print("Event pitches ready.")

    actor(engine, "admin")
    engine.mark_notifications_read()
    actor(engine, None)

    stats = engine.stats()
    print("Demo data complete.")
    print(f"Users {stats['users']} · posts {stats['posts']} · connections {stats['connections']} · events {stats['events']} · communities {stats['communities']}")
    print(f"Demo password for every seeded account: {PASSWORD}")
    print("Admin: admin / admin123")


if __name__ == "__main__":
    main()
