"""Vercel serverless entry point for CU-Kizuna."""

import seed_demo

from storage import db
from storage.blob_sync import blob_sync
from web.app import app

# Pull the shared database before seeding so warm instances see the same data.
blob_sync.download()
db.refresh_connection()
app.config["ENGINE"].reload()

try:
    seed_demo.main()
    app.config["ENGINE"].reload()
except Exception as exc:  # pragma: no cover - deployment safety net
    print(f"Seed skipped: {exc}")

db.checkpoint()
blob_sync.upload()

handler = app
