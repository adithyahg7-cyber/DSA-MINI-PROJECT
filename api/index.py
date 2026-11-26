"""Vercel serverless entry point for CU-Kizuna."""

import seed_demo

from web.app import app

# A fresh Vercel instance starts with an empty /tmp database, so populate the
# demo accounts, posts and events once per cold start.
try:
    seed_demo.main()
    # The app's Engine loaded its in-memory state before seeding, so refresh it.
    app.config["ENGINE"].reload()
except Exception as exc:  # pragma: no cover - deployment safety net
    print(f"Seed skipped: {exc}")

handler = app
