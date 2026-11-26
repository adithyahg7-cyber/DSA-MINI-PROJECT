from core.engine import Engine


def ask(label):
    return input(label).strip()


def show(result):
    if isinstance(result, tuple):
        if result and isinstance(result[0], bool):
            print("OK " if result[0] else "ERR", result[1])
            return result
    print(result)
    return result


def show_post(engine, post):
    likes = engine.like_count(post.post_id)
    comments = engine.comment_count(post.post_id)
    where = f" community={post.community_id}" if post.community_id else ""
    print(f"  #{post.post_id} {post.author}: {post.text}  [likes {likes}, comments {comments}]{where}")


def show_posts(engine, items):
    if not items:
        print("  (none)")
        return
    for post in items:
        show_post(engine, post)


def show_events(items):
    if not items:
        print("  (none)")
        return
    for event in items:
        print(f"  #{event.event_id} {event.date} {event.time} {event.title} @ {event.venue} by {event.organiser}")


def accounts(engine):
    while True:
        print("\n-- Accounts --")
        print("1 signup  2 login  3 logout  4 whoami  5 edit profile")
        print("6 change password  7 change username  0 back")
        choice = ask("> ")
        if choice == "1":
            username = ask("username: ")
            name = ask("full name: ")
            password = ask("password: ")
            show(engine.signup(username, name, password))
        elif choice == "2":
            show(engine.login(ask("username: "), ask("password: ")))
        elif choice == "3":
            show(engine.logout())
        elif choice == "4":
            print("  logged in as", engine.me)
        elif choice == "5":
            name = ask("new name (blank keeps): ")
            bio = ask("new bio (blank keeps): ")
            show(engine.update_profile(name or None, bio or None))
        elif choice == "6":
            show(engine.change_password(ask("old password: "), ask("new password: ")))
        elif choice == "7":
            show(engine.change_username(ask("new username: ")))
        elif choice == "0":
            return


def connections(engine):
    while True:
        print("\n-- Connections --")
        print("1 send  2 pending  3 accept  4 reject  5 cancel  6 remove")
        print("7 mutual  8 degree  9 chain  10 suggestions  11 search users  0 back")
        choice = ask("> ")
        if choice == "1":
            show(engine.send_request(ask("username: ")))
        elif choice == "2":
            result = engine.pending_requests()
            if isinstance(result, tuple):
                show(result)
            else:
                incoming, outgoing = result
                print("  incoming:", incoming or "(none)")
                print("  outgoing:", outgoing or "(none)")
        elif choice == "3":
            show(engine.accept_request(ask("sender: ")))
        elif choice == "4":
            show(engine.reject_request(ask("sender: ")))
        elif choice == "5":
            show(engine.cancel_request(ask("receiver: ")))
        elif choice == "6":
            show(engine.remove_connection(ask("username: ")))
        elif choice == "7":
            print(" ", engine.mutual_connections(ask("username: ")))
        elif choice == "8":
            print(" ", engine.connection_degree(ask("username: ")))
        elif choice == "9":
            print(" ", engine.shortest_chain(ask("username: ")))
        elif choice == "10":
            print(" ", engine.people_you_may_know())
        elif choice == "11":
            print(" ", engine.search_users(ask("prefix: ")))
        elif choice == "0":
            return


def posts_menu(engine):
    while True:
        print("\n-- Posts --")
        print("1 create  2 my posts  3 delete  4 explore feed  5 connections feed")
        print("6 like  7 unlike  8 comment  9 comments  10 trending  11 save")
        print("12 unsave  13 saved  14 report  0 back")
        choice = ask("> ")
        if choice == "1":
            show(engine.create_post(ask("text: ")))
        elif choice == "2":
            result = engine.own_posts()
            if isinstance(result, tuple):
                show(result)
            else:
                show_posts(engine, result)
        elif choice == "3":
            show(engine.delete_post(int(ask("post id: "))))
        elif choice == "4":
            page = int(ask("page: ") or 0)
            show_posts(engine, engine.explore_feed(page))
        elif choice == "5":
            result = engine.connections_feed(int(ask("page: ") or 0))
            if isinstance(result, tuple):
                show(result)
            else:
                show_posts(engine, result)
        elif choice == "6":
            show(engine.like_post(int(ask("post id: "))))
        elif choice == "7":
            show(engine.unlike_post(int(ask("post id: "))))
        elif choice == "8":
            post_id = int(ask("post id: "))
            parent = ask("reply to comment id (blank for top level): ")
            show(engine.add_comment(post_id, ask("text: "), int(parent) if parent else None))
        elif choice == "9":
            tree = engine.comment_tree(int(ask("post id: ")))
            for node in tree:
                print("  -", node["comment"].author, ":", node["comment"].text)
                for reply in node["replies"]:
                    print("      reply:", reply["comment"].author, ":", reply["comment"].text)
        elif choice == "10":
            result = engine.trending_posts()
            if isinstance(result, tuple):
                show(result)
            else:
                for post, score in result:
                    print(f"  score {score} | #{post.post_id} {post.author}: {post.text}")
        elif choice == "11":
            show(engine.save_post(int(ask("post id: "))))
        elif choice == "12":
            show(engine.unsave_post(int(ask("post id: "))))
        elif choice == "13":
            result = engine.saved_posts()
            if isinstance(result, tuple):
                show(result)
            else:
                show_posts(engine, result)
        elif choice == "14":
            show(engine.report_post(int(ask("post id: ")), ask("reason: ")))
        elif choice == "0":
            return


def notifications_menu(engine):
    while True:
        print("\n-- Notifications --")
        print("1 list  2 unread only  3 mark all read  4 mark one read  0 back")
        choice = ask("> ")
        if choice == "1":
            result = engine.notifications()
            if isinstance(result, tuple):
                show(result)
            else:
                for note in result:
                    print("  ", "read" if note.is_read else "new", note.text)
        elif choice == "2":
            result = engine.notifications(True)
            if isinstance(result, tuple):
                show(result)
            else:
                for note in result:
                    print("  ", note.text)
        elif choice == "3":
            show(engine.mark_notifications_read())
        elif choice == "4":
            show(engine.mark_notifications_read(int(ask("notification id: "))))
        elif choice == "0":
            return


def events_menu(engine):
    while True:
        print("\n-- Events --")
        print("1 add  2 events on date  3 upcoming  4 upload media  5 catalog")
        print("6 propose pitch  7 pitches  8 review pitch  9 rsvp  10 cancel rsvp")
        print("11 attendees  0 back")
        choice = ask("> ")
        if choice == "1":
            show(engine.add_event(
                ask("title: "),
                ask("description: "),
                ask("date YYYY-MM-DD: "),
                ask("time HH:MM: "),
                ask("venue: "),
            ))
        elif choice == "2":
            show_events(engine.events_on(ask("date YYYY-MM-DD: ")))
        elif choice == "3":
            show_events(engine.upcoming_events())
        elif choice == "4":
            show(engine.upload_media(int(ask("event id: ")), ask("file path: ")))
        elif choice == "5":
            items = engine.catalog_for(int(ask("event id: ")))
            for media in items:
                print(f"  {media.path} by {media.uploader}")
        elif choice == "6":
            show(engine.propose_pitch(ask("title: "), ask("description: ")))
        elif choice == "7":
            result = engine.pitches()
            if isinstance(result, tuple) and len(result) == 3:
                if not result[0]:
                    show(result)
                else:
                    for pitch in result[2]:
                        print(f"  #{pitch.pitch_id} {pitch.status} {pitch.title} by {pitch.proposer}")
            else:
                show(result)
        elif choice == "8":
            show(engine.review_pitch(int(ask("pitch id: ")), ask("approve/reject: ")))
        elif choice == "9":
            show(engine.rsvp(int(ask("event id: "))))
        elif choice == "10":
            show(engine.cancel_rsvp(int(ask("event id: "))))
        elif choice == "11":
            event_id = int(ask("event id: "))
            print("  going:", engine.attendee_count(event_id), sorted(engine.attendees(event_id)))
        elif choice == "0":
            return


def communities_menu(engine):
    while True:
        print("\n-- Communities --")
        print("1 create club  2 create group  3 list  4 join  5 approve  6 reject")
        print("7 leave  8 feed  9 post  10 members  11 pending  12 assign organiser  0 back")
        choice = ask("> ")
        if choice == "1":
            show(engine.create_club(ask("club name: ")))
        elif choice == "2":
            show(engine.create_group(ask("group name: "), ask("public/private: ")))
        elif choice == "3":
            result = engine.list_communities()
            if isinstance(result, tuple):
                show(result)
            else:
                for item in result:
                    community = item["community"]
                    print(f"  #{community.community_id} {community.name} {community.kind}/{community.visibility} joined={item['joined']} pending={item['pending']}")
        elif choice == "4":
            show(engine.join_community(int(ask("community id: "))))
        elif choice == "5":
            show(engine.approve_join(int(ask("community id: ")), ask("username: ")))
        elif choice == "6":
            show(engine.reject_join(int(ask("community id: ")), ask("username: ")))
        elif choice == "7":
            show(engine.leave_community(int(ask("community id: "))))
        elif choice == "8":
            result = engine.community_feed(int(ask("community id: ")))
            if isinstance(result, tuple) and len(result) == 3:
                if result[0]:
                    show_posts(engine, result[2])
                else:
                    show(result)
            else:
                show(result)
        elif choice == "9":
            show(engine.post_to_community(int(ask("community id: ")), ask("text: ")))
        elif choice == "10":
            print(" ", engine.community_members(int(ask("community id: "))))
        elif choice == "11":
            print(" ", engine.community_pending(int(ask("community id: "))))
        elif choice == "12":
            show(engine.assign_organiser(int(ask("community id: ")), ask("username: ")))
        elif choice == "0":
            return


def admin_menu(engine):
    while True:
        print("\n-- Admin --")
        print("1 set role  2 role log  3 moderation queue  4 review report  0 back")
        choice = ask("> ")
        if choice == "1":
            show(engine.set_role(ask("username: "), ask("student/organiser/admin: ")))
        elif choice == "2":
            for entry in engine.role_log():
                print(f"  {entry['actor']} changed {entry['target']} {entry['old_role']} -> {entry['new_role']}")
        elif choice == "3":
            result = engine.moderation_queue()
            if isinstance(result, tuple) and len(result) == 3:
                if result[0]:
                    for report in result[2]:
                        print(f"  #{report.report_id} post {report.post_id} by {report.reporter}: {report.reason}")
                else:
                    show(result)
            else:
                show(result)
        elif choice == "4":
            show(engine.review_report(int(ask("report id: ")), ask("dismiss/remove: ")))
        elif choice == "0":
            return


def main():
    engine = Engine()
    print("CU-Kizuna backend console")
    print("seeded admin:", engine.state.users.get("admin").username if "admin" in engine.state.users else "none")
    while True:
        print("\n== Main ==")
        print("1 accounts  2 connections  3 posts  4 notifications")
        print("5 events  6 communities  7 admin  0 exit")
        choice = ask("> ")
        if choice == "1":
            accounts(engine)
        elif choice == "2":
            connections(engine)
        elif choice == "3":
            posts_menu(engine)
        elif choice == "4":
            notifications_menu(engine)
        elif choice == "5":
            events_menu(engine)
        elif choice == "6":
            communities_menu(engine)
        elif choice == "7":
            admin_menu(engine)
        elif choice == "0":
            print("bye")
            return


if __name__ == "__main__":
    main()
