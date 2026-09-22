import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(2 * 1024**3)))
WHITELIST = {x.strip() for x in os.getenv("WHITELIST", "").split(",") if x.strip()}
WORK_DIR = BASE_DIR / "data"
USERS_FILE = WORK_DIR / "users.txt"
SETTINGS_FILE = WORK_DIR / "settings.txt"
ACCOUNTS_FILE = WORK_DIR / "accounts.txt"

def is_allowed(user_id: int) -> bool:
    return not WHITELIST or str(user_id) in WHITELIST
