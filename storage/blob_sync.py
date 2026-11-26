"""Sync the SQLite database file to Vercel Blob so serverless instances share state."""

import json
import os
import urllib.error
import urllib.request

import config


class BlobSync:
    def __init__(self):
        self.token = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
        self.store_id = os.environ.get("BLOB_STORE_ID", "")
        self.path = os.environ.get("BLOB_DB_PATH", "cu-kizuna/campus.db").lstrip("/")
        self.enabled = bool(os.environ.get("VERCEL") and self.token and self.store_id)
        store_host = self.store_id.removeprefix("store_").lower()
        self.download_url = f"https://{store_host}.private.blob.vercel-storage.com/{self.path}"
        self.upload_url = "https://blob.vercel-storage.com/" + self.path
        self.local_path = config.DB_PATH
        self.etag = None

    def download(self):
        """Pull the latest database file into /tmp. Returns True when it changed."""
        if not self.enabled:
            return False
        request = urllib.request.Request(
            self.download_url,
            headers={"Authorization": "Bearer " + self.token},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                remote = response.read()
                self.etag = response.headers.get("ETag")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            return False
        except Exception:
            return False

        try:
            with open(self.local_path, "rb") as handle:
                if handle.read() == remote:
                    return False
        except OSError:
            pass
        os.makedirs(os.path.dirname(self.local_path) or ".", exist_ok=True)
        with open(self.local_path, "wb") as handle:
            handle.write(remote)
        return True

    def upload(self):
        """Push the local database file back to Blob."""
        if not self.enabled:
            return False
        try:
            with open(self.local_path, "rb") as handle:
                payload = handle.read()
        except OSError:
            return False
        request = urllib.request.Request(
            self.upload_url,
            data=payload,
            method="PUT",
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/octet-stream",
                "x-content-type": "application/octet-stream",
                "x-vercel-blob-access": "private",
                "x-add-random-suffix": "0",
                "x-allow-overwrite": "1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8") or "{}")
                self.etag = result.get("etag", self.etag)
                return True
        except Exception:
            return False


blob_sync = BlobSync()
