"""
Модуль работы с SQLite через aiosqlite.
Все операции асинхронные. Схема создаётся автоматически при первом запуске.
"""

import aiosqlite
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, AsyncIterator

from config import DB_PATH

logger = logging.getLogger(__name__)


def _ensure_db_dir() -> None:
    """Создаёт родительскую директорию для файла БД, если её нет."""
    db_path = Path(DB_PATH)
    parent = db_path.parent
    if parent and str(parent) not in (".", ""):
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(
                "Не удалось создать директорию для БД %s: %s. "
                "Проверьте, что Volume смонтирован на /data и DB_PATH=%s",
                parent, e, DB_PATH
            )
            raise


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Контекстный менеджер: открывает соединение с БД и закрывает его."""
    _ensure_db_dir()
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    """Создаёт все таблицы, если их ещё нет."""
    async with get_db() as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                balance     REAL DEFAULT 0.0,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS categories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                is_visible  INTEGER DEFAULT 1,
                sort_order  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS subcategories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name        TEXT NOT NULL,
                is_visible  INTEGER DEFAULT 1,
                sort_order  INTEGER DEFAULT 0,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS products (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                subcategory_id  INTEGER NOT NULL,
                name            TEXT NOT NULL,
                description     TEXT DEFAULT '',
                price           REAL NOT NULL,
                weight          TEXT DEFAULT '',
                photo_file_id   TEXT,
                stock           INTEGER DEFAULT 0,
                is_visible      INTEGER DEFAULT 1,
                FOREIGN KEY (subcategory_id) REFERENCES subcategories(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS cart_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                product_id  INTEGER NOT NULL,
                quantity    INTEGER DEFAULT 1,
                UNIQUE(user_id, product_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                total       REAL NOT NULL,
                status      TEXT DEFAULT 'new',
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id    INTEGER NOT NULL,
                product_id  INTEGER NOT NULL,
                quantity    INTEGER NOT NULL,
                price       REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS topups (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                amount          REAL,
                status          TEXT DEFAULT 'pending',
                receipt_file_id TEXT,
                receipt_type    TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                processed_at    TEXT,
                processed_by    INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS balance_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL NOT NULL,
                type        TEXT NOT NULL,
                description TEXT,
                related_id  INTEGER,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        # Дефолтные настройки
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("welcome_text", "🍬 Добро пожаловать в магазин домашнего мармелада!\n\n"
                             "Мы делаем натуральный мармелад с любовью. "
                             "Выбирайте вкусы, добавляйте в корзину и наслаждайтесь!")
        )
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("about_text", "🍬 О нашем магазине\n\n"
                           "Мы — небольшая семейная мастерская домашнего мармелада. "
                           "Только натуральные ингредиенты, никаких искусственных красителей. "
                           "Каждая партия готовится вручную с заботой о вас ❤️")
        )
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("wallet_address", "")
        )
        await db.commit()
        logger.info("База данных инициализирована: %s", DB_PATH)


# ─────────────────────────── Пользователи ───────────────────────────

async def ensure_user(user_id: int, username: Optional[str], full_name: str) -> None:
    async with get_db() as db:
        await db.execute(
            """INSERT INTO users (user_id, username, full_name)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   username = excluded.username,
                   full_name = excluded.full_name""",
            (user_id, username or "", full_name or "")
        )
        await db.commit()


async def get_user(user_id: int) -> Optional[Dict]:
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_balance(user_id: int) -> float:
    user = await get_user(user_id)
    return float(user["balance"]) if user else 0.0


async def change_balance(
    user_id: int,
    amount: float,
    typ: str,
    description: str = "",
    related_id: Optional[int] = None
) -> float:
    """Изменяет баланс и пишет историю. Возвращает новый баланс."""
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.execute(
            """INSERT INTO balance_history (user_id, amount, type, description, related_id)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, amount, typ, description, related_id)
        )
        await db.commit()
        cur = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return float(row["balance"]) if row else 0.0


async def search_users(query: str) -> List[Dict]:
    async with get_db() as db:
        if query.isdigit():
            cur = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (int(query),)
            )
        else:
            cur = await db.execute(
                "SELECT * FROM users WHERE username LIKE ? OR full_name LIKE ? LIMIT 20",
                (f"%{query}%", f"%{query}%")
            )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_all_user_ids() -> List[int]:
    async with get_db() as db:
        cur = await db.execute("SELECT user_id FROM users")
        rows = await cur.fetchall()
        return [r["user_id"] for r in rows]


# ─────────────────────────── Настройки ───────────────────────────

async def get_setting(key: str, default: str = "") -> str:
    async with get_db() as db:
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row["value"] if row else default


async def set_setting(key: str, value: str) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        await db.commit()


# ─────────────────────────── Категории ───────────────────────────

async def get_categories(only_visible: bool = True) -> List[Dict]:
    async with get_db() as db:
        if only_visible:
            cur = await db.execute(
                "SELECT * FROM categories WHERE is_visible = 1 ORDER BY sort_order, id"
            )
        else:
            cur = await db.execute(
                "SELECT * FROM categories ORDER BY sort_order, id"
            )
        return [dict(r) for r in await cur.fetchall()]


async def get_category(cat_id: int) -> Optional[Dict]:
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM categories WHERE id = ?", (cat_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_category(name: str) -> int:
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO categories (name) VALUES (?)", (name,)
        )
        await db.commit()
        return cur.lastrowid


async def rename_category(cat_id: int, name: str) -> None:
    async with get_db() as db:
        await db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, cat_id))
        await db.commit()


async def delete_category(cat_id: int) -> None:
    async with get_db() as db:
        await db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        await db.commit()


async def toggle_category_visibility(cat_id: int) -> bool:
    async with get_db() as db:
        cur = await db.execute("SELECT is_visible FROM categories WHERE id = ?", (cat_id,))
        row = await cur.fetchone()
        if not row:
            return False
        new_val = 0 if row["is_visible"] else 1
        await db.execute(
            "UPDATE categories SET is_visible = ? WHERE id = ?", (new_val, cat_id)
        )
        await db.commit()
        return bool(new_val)


# ─────────────────────────── Подкатегории ───────────────────────────

async def get_subcategories(category_id: int, only_visible: bool = True) -> List[Dict]:
    async with get_db() as db:
        if only_visible:
            cur = await db.execute(
                "SELECT * FROM subcategories WHERE category_id = ? AND is_visible = 1 "
                "ORDER BY sort_order, id",
                (category_id,)
            )
        else:
            cur = await db.execute(
                "SELECT * FROM subcategories WHERE category_id = ? ORDER BY sort_order, id",
                (category_id,)
            )
        return [dict(r) for r in await cur.fetchall()]


async def get_subcategory(sub_id: int) -> Optional[Dict]:
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM subcategories WHERE id = ?", (sub_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_subcategory(category_id: int, name: str) -> int:
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO subcategories (category_id, name) VALUES (?, ?)",
            (category_id, name)
        )
        await db.commit()
        return cur.lastrowid


async def rename_subcategory(sub_id: int, name: str) -> None:
    async with get_db() as db:
        await db.execute("UPDATE subcategories SET name = ? WHERE id = ?", (name, sub_id))
        await db.commit()


async def delete_subcategory(sub_id: int) -> None:
    async with get_db() as db:
        await db.execute("DELETE FROM subcategories WHERE id = ?", (sub_id,))
        await db.commit()


async def toggle_subcategory_visibility(sub_id: int) -> bool:
    async with get_db() as db:
        cur = await db.execute("SELECT is_visible FROM subcategories WHERE id = ?", (sub_id,))
        row = await cur.fetchone()
        if not row:
            return False
        new_val = 0 if row["is_visible"] else 1
        await db.execute(
            "UPDATE subcategories SET is_visible = ? WHERE id = ?", (new_val, sub_id)
        )
        await db.commit()
        return bool(new_val)


# ─────────────────────────── Товары ───────────────────────────

async def get_products(subcategory_id: int, only_visible: bool = True) -> List[Dict]:
    async with get_db() as db:
        if only_visible:
            cur = await db.execute(
                "SELECT * FROM products WHERE subcategory_id = ? AND is_visible = 1 "
                "ORDER BY id",
                (subcategory_id,)
            )
        else:
            cur = await db.execute(
                "SELECT * FROM products WHERE subcategory_id = ? ORDER BY id",
                (subcategory_id,)
            )
        return [dict(r) for r in await cur.fetchall()]


async def get_product(product_id: int) -> Optional[Dict]:
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_product(
    subcategory_id: int,
    name: str,
    description: str,
    price: float,
    weight: str,
    photo_file_id: Optional[str],
    stock: int
) -> int:
    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO products
               (subcategory_id, name, description, price, weight, photo_file_id, stock)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (subcategory_id, name, description, price, weight, photo_file_id, stock)
        )
        await db.commit()
        return cur.lastrowid


async def update_product_field(product_id: int, field: str, value: Any) -> None:
    allowed = {"name", "description", "price", "weight", "photo_file_id", "stock", "is_visible", "subcategory_id"}
    if field not in allowed:
        raise ValueError(f"Недопустимое поле: {field}")
    async with get_db() as db:
        await db.execute(
            f"UPDATE products SET {field} = ? WHERE id = ?", (value, product_id)
        )
        await db.commit()


async def delete_product(product_id: int) -> None:
    async with get_db() as db:
        await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await db.commit()


async def toggle_product_visibility(product_id: int) -> bool:
    async with get_db() as db:
        cur = await db.execute("SELECT is_visible FROM products WHERE id = ?", (product_id,))
        row = await cur.fetchone()
        if not row:
            return False
        new_val = 0 if row["is_visible"] else 1
        await db.execute(
            "UPDATE products SET is_visible = ? WHERE id = ?", (new_val, product_id)
        )
        await db.commit()
        return bool(new_val)


async def decrease_stock(product_id: int, qty: int) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE products SET stock = MAX(0, stock - ?) WHERE id = ?",
            (qty, product_id)
        )
        await db.commit()


# ─────────────────────────── Корзина ───────────────────────────

async def get_cart(user_id: int) -> List[Dict]:
    async with get_db() as db:
        cur = await db.execute(
            """SELECT ci.id, ci.quantity, p.id as product_id, p.name, p.price,
                      p.weight, p.stock, p.photo_file_id
               FROM cart_items ci
               JOIN products p ON p.id = ci.product_id
               WHERE ci.user_id = ?""",
            (user_id,)
        )
        return [dict(r) for r in await cur.fetchall()]


async def add_to_cart(user_id: int, product_id: int, quantity: int = 1) -> None:
    async with get_db() as db:
        await db.execute(
            """INSERT INTO cart_items (user_id, product_id, quantity)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, product_id) DO UPDATE SET
                   quantity = quantity + excluded.quantity""",
            (user_id, product_id, quantity)
        )
        await db.commit()


async def set_cart_quantity(user_id: int, product_id: int, quantity: int) -> None:
    async with get_db() as db:
        if quantity <= 0:
            await db.execute(
                "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
                (user_id, product_id)
            )
        else:
            await db.execute(
                "UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?",
                (quantity, user_id, product_id)
            )
        await db.commit()


async def remove_from_cart(user_id: int, product_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id)
        )
        await db.commit()


async def clear_cart(user_id: int) -> None:
    async with get_db() as db:
        await db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_cart_total(user_id: int) -> float:
    items = await get_cart(user_id)
    return sum(item["price"] * item["quantity"] for item in items)


# ─────────────────────────── Заказы ───────────────────────────

STATUS_MAP = {
    "new": "🆕 Новый",
    "assembling": "🛠 Собирается",
    "shipped": "📦 Отправлен",
    "completed": "✅ Выполнен",
    "cancelled": "❌ Отменён",
}


async def create_order(user_id: int, cart_items: List[Dict]) -> int:
    total = sum(i["price"] * i["quantity"] for i in cart_items)
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO orders (user_id, total, status) VALUES (?, ?, 'new')",
            (user_id, total)
        )
        order_id = cur.lastrowid
        for item in cart_items:
            await db.execute(
                """INSERT INTO order_items (order_id, product_id, quantity, price)
                   VALUES (?, ?, ?, ?)""",
                (order_id, item["product_id"], item["quantity"], item["price"])
            )
            await db.execute(
                "UPDATE products SET stock = MAX(0, stock - ?) WHERE id = ?",
                (item["quantity"], item["product_id"])
            )
        await db.commit()
    return order_id


async def get_user_orders(user_id: int) -> List[Dict]:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 30",
            (user_id,)
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_order(order_id: int) -> Optional[Dict]:
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_order_items(order_id: int) -> List[Dict]:
    async with get_db() as db:
        cur = await db.execute(
            """SELECT oi.*, p.name
               FROM order_items oi
               JOIN products p ON p.id = oi.product_id
               WHERE oi.order_id = ?""",
            (order_id,)
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_orders_by_status(status: str = "new") -> List[Dict]:
    async with get_db() as db:
        cur = await db.execute(
            """SELECT o.*, u.username, u.full_name
               FROM orders o
               JOIN users u ON u.user_id = o.user_id
               WHERE o.status = ?
               ORDER BY o.id DESC LIMIT 50""",
            (status,)
        )
        return [dict(r) for r in await cur.fetchall()]


async def update_order_status(order_id: int, status: str) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE orders SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, order_id)
        )
        await db.commit()


# ─────────────────────────── Заявки на пополнение ───────────────────────────

async def create_topup(
    user_id: int,
    receipt_file_id: str,
    receipt_type: str
) -> int:
    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO topups (user_id, status, receipt_file_id, receipt_type)
               VALUES (?, 'pending', ?, ?)""",
            (user_id, receipt_file_id, receipt_type)
        )
        await db.commit()
        return cur.lastrowid


async def get_topup(topup_id: int) -> Optional[Dict]:
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM topups WHERE id = ?", (topup_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_pending_topups() -> List[Dict]:
    async with get_db() as db:
        cur = await db.execute(
            """SELECT t.*, u.username, u.full_name
               FROM topups t
               JOIN users u ON u.user_id = t.user_id
               WHERE t.status = 'pending'
               ORDER BY t.id DESC"""
        )
        return [dict(r) for r in await cur.fetchall()]


async def process_topup(
    topup_id: int,
    status: str,
    admin_id: int,
    amount: Optional[float] = None
) -> bool:
    """Обрабатывает заявку. Возвращает False, если уже обработана."""
    async with get_db() as db:
        cur = await db.execute(
            "SELECT status FROM topups WHERE id = ?", (topup_id,)
        )
        row = await cur.fetchone()
        if not row or row["status"] != "pending":
            return False
        await db.execute(
            """UPDATE topups SET status = ?, amount = ?, processed_at = datetime('now'),
               processed_by = ? WHERE id = ?""",
            (status, amount, admin_id, topup_id)
        )
        await db.commit()
        return True
