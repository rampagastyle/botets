import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    try:
        return int(str(raw).strip() or default)
    except (TypeError, ValueError):
        return int(default)


# Hobby ~8GB: 2 GiB limit on source, up to 3 concurrent jobs
MAX_FILE_SIZE = _env_int("MAX_FILE_SIZE", 2 * 1024 * 1024 * 1024)
MAX_CONCURRENT_JOBS = _env_int("MAX_CONCURRENT_JOBS", 3)

ADMIN_IDS = {x.strip() for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
ENV_WHITELIST = {x.strip() for x in os.getenv("WHITELIST", "").split(",") if x.strip()}

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

WORK_DIR = BASE_DIR / "data"
BANNERS_DIR = WORK_DIR / "banners"
BANNERS_INDEX = BANNERS_DIR / "index.json"
USERS_FILE = WORK_DIR / "users.txt"
SETTINGS_FILE = WORK_DIR / "settings.txt"
ACCOUNTS_FILE = WORK_DIR / "accounts.txt"
WHITELIST_FILE = WORK_DIR / "whitelist.txt"


def is_admin(user_id: int) -> bool:
    return str(user_id) in ADMIN_IDS
