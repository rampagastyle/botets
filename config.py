import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Лимит входного файла. На бесплатном хостинге лучше не разрешать
# бесконечно большие исходники.
MAX_FILE_SIZE = int(
    os.getenv("MAX_FILE_SIZE", str(1024 * 1024 * 1024))
)

ADMIN_IDS = {
    x.strip()
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip()
}

ENV_WHITELIST = {
    x.strip()
    for x in os.getenv("WHITELIST", "").split(",")
    if x.strip()
}

WORK_DIR = BASE_DIR / "data"
USERS_FILE = WORK_DIR / "users.txt"
SETTINGS_FILE = WORK_DIR / "settings.txt"
ACCOUNTS_FILE = WORK_DIR / "accounts.txt"
WHITELIST_FILE = WORK_DIR / "whitelist.txt"


def is_admin(user_id: int) -> bool:
    return str(user_id) in ADMIN_IDS
