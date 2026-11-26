import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "campus.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_NAME = "CU-Kizuna Admin"

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
