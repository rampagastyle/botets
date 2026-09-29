import os
from typing import List

# Токен бота (обязательная переменная)
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# Список ID администраторов (через запятую)
_admin_ids_raw: str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: List[int] = [
    int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()
]

# Путь к файлу SQLite (на Railway используем Volume)
DB_PATH: str = os.getenv("DB_PATH", "/data/shop.db")

# Проверка обязательных переменных при импорте
if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")
