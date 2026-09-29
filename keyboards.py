"""
Все inline-клавиатуры бота.
callback_data ограничены 64 байтами.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict, Optional


# ─────────────────────────── Пользовательские ───────────────────────────

def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛍 Каталог", callback_data="catalog"))
    builder.row(InlineKeyboardButton(text="🛒 Корзина", callback_data="cart"))
    builder.row(InlineKeyboardButton(text="💰 Баланс", callback_data="balance"))
    builder.row(InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders"))
    builder.row(InlineKeyboardButton(text="ℹ️ О магазине", callback_data="about"))
    return builder.as_markup()


def categories_kb(categories: List[Dict], admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        prefix = "" if cat.get("is_visible", 1) else "🙈 "
        builder.row(
            InlineKeyboardButton(
                text=f"{prefix}{cat['name']}",
                callback_data=f"cat:{cat['id']}"
            )
        )
    if admin:
        builder.row(InlineKeyboardButton(text="➕ Добавить категорию", callback_data="adm_cat_add"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def subcategories_kb(
    subcategories: List[Dict],
    category_id: int,
    admin: bool = False
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sub in subcategories:
        prefix = "" if sub.get("is_visible", 1) else "🙈 "
        builder.row(
            InlineKeyboardButton(
                text=f"{prefix}{sub['name']}",
                callback_data=f"sub:{sub['id']}"
            )
        )
    if admin:
        builder.row(
            InlineKeyboardButton(
                text="➕ Добавить раздел",
                callback_data=f"adm_sub_add:{category_id}"
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="catalog"))
    return builder.as_markup()


def products_kb(
    products: List[Dict],
    subcategory_id: int,
    category_id: int,
    admin: bool = False
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in products:
        prefix = "" if p.get("is_visible", 1) else "🙈 "
        stock_info = f" (остаток: {p['stock']})" if admin else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{prefix}{p['name']} — {p['price']:.0f} ₽{stock_info}",
                callback_data=f"prod:{p['id']}"
            )
        )
    if admin:
        builder.row(
            InlineKeyboardButton(
                text="➕ Добавить товар",
                callback_data=f"adm_prod_add:{subcategory_id}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"cat:{category_id}")
    )
    return builder.as_markup()


def product_card_kb(product_id: int, subcategory_id: int, in_cart: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🛒 Добавить в корзину",
            callback_data=f"add_cart:{product_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"sub:{subcategory_id}")
    )
    return builder.as_markup()


def cart_kb(items: List[Dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        pid = item["product_id"]
        builder.row(
            InlineKeyboardButton(text="➖", callback_data=f"cart_minus:{pid}"),
            InlineKeyboardButton(
                text=f"{item['name'][:20]} × {item['quantity']}",
                callback_data=f"cart_info:{pid}"
            ),
            InlineKeyboardButton(text="➕", callback_data=f"cart_plus:{pid}"),
        )
        builder.row(
            InlineKeyboardButton(
                text=f"🗑 Удалить «{item['name'][:25]}»",
                callback_data=f"cart_del:{pid}"
            )
        )
    if items:
        builder.row(
            InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")
        )
    builder.row(InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu"))
    return builder.as_markup()


def balance_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Пополнить баланс", callback_data="topup_start")
    )
    builder.row(InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu"))
    return builder.as_markup()


def topup_paid_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="topup_paid")
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="balance"))
    return builder.as_markup()


def topup_cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="balance"))
    return builder.as_markup()


def insufficient_balance_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Пополнить баланс", callback_data="topup_start")
    )
    builder.row(InlineKeyboardButton(text="◀️ В корзину", callback_data="cart"))
    return builder.as_markup()


def my_orders_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu"))
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu"))
    return builder.as_markup()


# ─────────────────────────── Админские ───────────────────────────

def admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📁 Категории", callback_data="adm_cats"))
    builder.row(InlineKeyboardButton(text="📦 Заказы (новые)", callback_data="adm_orders:new"))
    builder.row(InlineKeyboardButton(text="💳 Заявки на пополнение", callback_data="adm_topups"))
    builder.row(InlineKeyboardButton(text="⚙️ Настройки", callback_data="adm_settings"))
    builder.row(InlineKeyboardButton(text="👤 Пользователи", callback_data="adm_users"))
    builder.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast"))
    builder.row(InlineKeyboardButton(text="◀️ В меню магазина", callback_data="main_menu"))
    return builder.as_markup()


def admin_categories_kb(categories: List[Dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        vis = "👁" if cat["is_visible"] else "🙈"
        builder.row(
            InlineKeyboardButton(
                text=f"{vis} {cat['name']}",
                callback_data=f"adm_cat:{cat['id']}"
            )
        )
    builder.row(InlineKeyboardButton(text="➕ Добавить", callback_data="adm_cat_add"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
    return builder.as_markup()


def admin_category_actions_kb(cat_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📂 Разделы", callback_data=f"adm_subs:{cat_id}")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"adm_cat_ren:{cat_id}"),
        InlineKeyboardButton(text="👁/🙈 Видимость", callback_data=f"adm_cat_vis:{cat_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_cat_del:{cat_id}")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="adm_cats"))
    return builder.as_markup()


def admin_subcategories_kb(subs: List[Dict], category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sub in subs:
        vis = "👁" if sub["is_visible"] else "🙈"
        builder.row(
            InlineKeyboardButton(
                text=f"{vis} {sub['name']}",
                callback_data=f"adm_sub:{sub['id']}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить раздел", callback_data=f"adm_sub_add:{category_id}")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_cat:{category_id}"))
    return builder.as_markup()


def admin_subcategory_actions_kb(sub_id: int, category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🍬 Товары", callback_data=f"adm_prods:{sub_id}")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"adm_sub_ren:{sub_id}"),
        InlineKeyboardButton(text="👁/🙈 Видимость", callback_data=f"adm_sub_vis:{sub_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_sub_del:{sub_id}")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_subs:{category_id}"))
    return builder.as_markup()


def admin_products_kb(products: List[Dict], subcategory_id: int, category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in products:
        vis = "👁" if p["is_visible"] else "🙈"
        builder.row(
            InlineKeyboardButton(
                text=f"{vis} {p['name']} — {p['price']:.0f} ₽ (ост: {p['stock']})",
                callback_data=f"adm_prod:{p['id']}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить товар", callback_data=f"adm_prod_add:{subcategory_id}")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_sub:{subcategory_id}"))
    return builder.as_markup()


def admin_product_actions_kb(product_id: int, subcategory_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Название", callback_data=f"adm_pedit:{product_id}:name"),
        InlineKeyboardButton(text="📝 Описание", callback_data=f"adm_pedit:{product_id}:description"),
    )
    builder.row(
        InlineKeyboardButton(text="💰 Цена", callback_data=f"adm_pedit:{product_id}:price"),
        InlineKeyboardButton(text="⚖️ Фасовка", callback_data=f"adm_pedit:{product_id}:weight"),
    )
    builder.row(
        InlineKeyboardButton(text="🖼 Фото", callback_data=f"adm_pedit:{product_id}:photo"),
        InlineKeyboardButton(text="📦 Остаток", callback_data=f"adm_pedit:{product_id}:stock"),
    )
    builder.row(
        InlineKeyboardButton(text="👁/🙈 Видимость", callback_data=f"adm_prod_vis:{product_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_prod_del:{product_id}"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_prods:{subcategory_id}"))
    return builder.as_markup()


def admin_orders_kb(orders: List[Dict], status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for o in orders:
        uname = o.get("username") or o.get("full_name") or str(o["user_id"])
        builder.row(
            InlineKeyboardButton(
                text=f"#{o['id']} — {o['total']:.0f} ₽ — @{uname}",
                callback_data=f"adm_ord:{o['id']}"
            )
        )
    # Переключатели статусов
    statuses = [
        ("new", "🆕 Новые"),
        ("assembling", "🛠 Сборка"),
        ("shipped", "📦 Отправлены"),
        ("completed", "✅ Выполнены"),
        ("cancelled", "❌ Отменённые"),
    ]
    row = []
    for s, label in statuses:
        mark = "• " if s == status else ""
        row.append(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"adm_orders:{s}"))
        if len(row) == 2:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
    return builder.as_markup()


def admin_order_actions_kb(order_id: int, current_status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    transitions = {
        "new": [("assembling", "🛠 Собирается"), ("cancelled", "❌ Отменить")],
        "assembling": [("shipped", "📦 Отправлен"), ("cancelled", "❌ Отменить")],
        "shipped": [("completed", "✅ Выполнен"), ("cancelled", "❌ Отменить")],
        "completed": [],
        "cancelled": [],
    }
    for st, label in transitions.get(current_status, []):
        builder.row(
            InlineKeyboardButton(text=label, callback_data=f"adm_ord_st:{order_id}:{st}")
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="adm_orders:new"))
    return builder.as_markup()


def admin_topups_kb(topups: List[Dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in topups:
        uname = t.get("username") or t.get("full_name") or str(t["user_id"])
        builder.row(
            InlineKeyboardButton(
                text=f"#{t['id']} — @{uname}",
                callback_data=f"adm_top:{t['id']}"
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
    return builder.as_markup()


def admin_topup_actions_kb(topup_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Добавить баланс", callback_data=f"adm_top_ok:{topup_id}"),
        InlineKeyboardButton(text="❌ Отказать", callback_data=f"adm_top_no:{topup_id}"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="adm_topups"))
    return builder.as_markup()


def admin_settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Адрес кошелька", callback_data="adm_set_wallet")
    )
    builder.row(
        InlineKeyboardButton(text="👋 Текст приветствия", callback_data="adm_set_welcome")
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ Текст «О магазине»", callback_data="adm_set_about")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
    return builder.as_markup()


def confirm_kb(yes_data: str, no_data: str = "admin_panel") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=yes_data),
        InlineKeyboardButton(text="❌ Нет", callback_data=no_data),
    )
    return builder.as_markup()


def cancel_kb(callback: str = "admin_panel") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=callback))
    return builder.as_markup()


def admin_user_kb(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Начислить", callback_data=f"adm_ubal:{user_id}:add"),
        InlineKeyboardButton(text="➖ Списать", callback_data=f"adm_ubal:{user_id}:sub"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="adm_users"))
    return builder.as_markup()
