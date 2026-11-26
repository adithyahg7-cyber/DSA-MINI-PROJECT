import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Vercel serverless functions have a read-only project filesystem; use /tmp for
# the SQLite database and uploaded media there. Local development stays in the
# project directory.
DATA_DIR = "/tmp" if os.environ.get("VERCEL") else BASE_DIR

DB_PATH = os.path.join(DATA_DIR, "campus.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_NAME = "CU-connect Admin"

PAGE_SIZE = 10
TRENDING_DAYS = 7
MAX_CHAIN_DEPTH = 3
SUGGESTION_LIMIT = 10
SEARCH_LIMIT = 10

USERNAME_MIN = 3
USERNAME_MAX = 20
PASSWORD_MIN = 6

ROLES = ("student", "organiser", "admin")
VISIBILITIES = ("public", "private")
