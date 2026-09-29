"""
Админ-панель: категории, разделы, товары, заказы, заявки, настройки,
пользователи, рассылка.
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import database as db
from keyboards import (
    admin_main_kb, admin_categories_kb, admin_category_actions_kb,
    admin_subcategories_kb, admin_subcategory_actions_kb,
    admin_products_kb, admin_product_actions_kb,
    admin_orders_kb, admin_order_actions_kb,
    admin_topups_kb, admin_topup_actions_kb,
    admin_settings_kb, confirm_kb, cancel_kb, admin_user_kb,
    back_to_menu_kb
)
from states import (
    AdminCategoryStates, AdminSubcategoryStates, AdminProductStates,
    AdminTopupStates, AdminSettingsStates, AdminUserStates,
    AdminBroadcastStates
)
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─────────────────────────── Вход в админку ───────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await state.clear()
    await message.answer(
        "🔧 <b>Админ-панель</b>\n\nВыберите раздел:",
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "🔧 <b>Админ-панель</b>\n\nВыберите раздел:",
        reply_markup=admin_main_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ─────────────────────────── Категории ───────────────────────────

@router.callback_query(F.data == "adm_cats")
async def cb_adm_cats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    cats = await db.get_categories(only_visible=False)
    await callback.message.edit_text(
        "📁 <b>Категории</b>",
        reply_markup=admin_categories_kb(cats),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "adm_cat_add")
async def cb_adm_cat_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminCategoryStates.add_name)
    await callback.message.edit_text(
        "Введите название новой категории:",
        reply_markup=cancel_kb("adm_cats")
    )
    await callback.answer()


@router.message(AdminCategoryStates.add_name)
async def process_cat_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if not name or len(name) > 100:
        await message.answer("Название должно быть от 1 до 100 символов. Попробуйте ещё раз:")
        return
    await db.add_category(name)
    await state.clear()
    await message.answer(f"✅ Категория «{name}» создана!", reply_markup=admin_main_kb())


@router.callback_query(F.data.startswith("adm_cat:"))
async def cb_adm_cat(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cat_id = int(callback.data.split(":")[1])
    cat = await db.get_category(cat_id)
    if not cat:
        await callback.answer("Не найдено", show_alert=True)
        return
    vis = "видима" if cat["is_visible"] else "скрыта"
    await callback.message.edit_text(
        f"📁 <b>{cat['name']}</b>\nСтатус: {vis}",
        reply_markup=admin_category_actions_kb(cat_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_cat_ren:"))
async def cb_adm_cat_ren(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    cat_id = int(callback.data.split(":")[1])
    await state.set_state(AdminCategoryStates.rename)
    await state.update_data(cat_id=cat_id)
    await callback.message.edit_text(
        "Введите новое название категории:",
        reply_markup=cancel_kb(f"adm_cat:{cat_id}")
    )
    await callback.answer()


@router.message(AdminCategoryStates.rename)
async def process_cat_rename(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    name = message.text.strip()
    if not name or len(name) > 100:
        await message.answer("Некорректное название. Попробуйте ещё раз:")
        return
    await db.rename_category(data["cat_id"], name)
    await state.clear()
    await message.answer(f"✅ Переименовано в «{name}»", reply_markup=admin_main_kb())


@router.callback_query(F.data.startswith("adm_cat_vis:"))
async def cb_adm_cat_vis(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cat_id = int(callback.data.split(":")[1])
    new_vis = await db.toggle_category_visibility(cat_id)
    status = "показана" if new_vis else "скрыта"
    await callback.answer(f"Категория {status}")
    # Обновляем экран
    cat = await db.get_category(cat_id)
    vis = "видима" if cat["is_visible"] else "скрыта"
    await callback.message.edit_text(
        f"📁 <b>{cat['name']}</b>\nСтатус: {vis}",
        reply_markup=admin_category_actions_kb(cat_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_cat_del:"))
async def cb_adm_cat_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cat_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "⚠️ Удалить категорию вместе со всеми разделами и товарами?",
        reply_markup=confirm_kb(f"adm_cat_del_ok:{cat_id}", f"adm_cat:{cat_id}")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_cat_del_ok:"))
async def cb_adm_cat_del_ok(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cat_id = int(callback.data.split(":")[1])
    await db.delete_category(cat_id)
    await callback.answer("Удалено")
    cats = await db.get_categories(only_visible=False)
    await callback.message.edit_text(
        "📁 <b>Категории</b>",
        reply_markup=admin_categories_kb(cats),
        parse_mode="HTML"
    )


# ─────────────────────────── Разделы ───────────────────────────

@router.callback_query(F.data.startswith("adm_subs:"))
async def cb_adm_subs(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cat_id = int(callback.data.split(":")[1])
    subs = await db.get_subcategories(cat_id, only_visible=False)
    cat = await db.get_category(cat_id)
    await callback.message.edit_text(
        f"📂 Разделы категории «{cat['name'] if cat else '?'}»",
        reply_markup=admin_subcategories_kb(subs, cat_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_sub_add:"))
async def cb_adm_sub_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    cat_id = int(callback.data.split(":")[1])
    await state.set_state(AdminSubcategoryStates.add_name)
    await state.update_data(category_id=cat_id)
    await callback.message.edit_text(
        "Введите название нового раздела:",
        reply_markup=cancel_kb(f"adm_subs:{cat_id}")
    )
    await callback.answer()


@router.message(AdminSubcategoryStates.add_name)
async def process_sub_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    name = message.text.strip()
    if not name or len(name) > 100:
        await message.answer("Некорректное название:")
        return
    await db.add_subcategory(data["category_id"], name)
    await state.clear()
    await message.answer(f"✅ Раздел «{name}» создан!", reply_markup=admin_main_kb())


@router.callback_query(F.data.startswith("adm_sub:"))
async def cb_adm_sub(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    # adm_sub:ID  или adm_sub_ren:ID и т.д. — обрабатываем только точный
    parts = callback.data.split(":")
    if len(parts) != 2 or not parts[1].isdigit():
        return
    sub_id = int(parts[1])
    sub = await db.get_subcategory(sub_id)
    if not sub:
        await callback.answer("Не найдено", show_alert=True)
        return
    vis = "видим" if sub["is_visible"] else "скрыт"
    await callback.message.edit_text(
        f"📂 <b>{sub['name']}</b>\nСтатус: {vis}",
        reply_markup=admin_subcategory_actions_kb(sub_id, sub["category_id"]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_sub_ren:"))
async def cb_adm_sub_ren(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    sub_id = int(callback.data.split(":")[1])
    await state.set_state(AdminSubcategoryStates.rename)
    await state.update_data(sub_id=sub_id)
    await callback.message.edit_text(
        "Введите новое название раздела:",
        reply_markup=cancel_kb(f"adm_sub:{sub_id}")
    )
    await callback.answer()


@router.message(AdminSubcategoryStates.rename)
async def process_sub_rename(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    name = message.text.strip()
    if not name or len(name) > 100:
        await message.answer("Некорректное название:")
        return
    await db.rename_subcategory(data["sub_id"], name)
    await state.clear()
    await message.answer(f"✅ Переименовано в «{name}»", reply_markup=admin_main_kb())


@router.callback_query(F.data.startswith("adm_sub_vis:"))
async def cb_adm_sub_vis(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    sub_id = int(callback.data.split(":")[1])
    new_vis = await db.toggle_subcategory_visibility(sub_id)
    await callback.answer("Показан" if new_vis else "Скрыт")
    sub = await db.get_subcategory(sub_id)
    vis = "видим" if sub["is_visible"] else "скрыт"
    await callback.message.edit_text(
        f"📂 <b>{sub['name']}</b>\nСтатус: {vis}",
        reply_markup=admin_subcategory_actions_kb(sub_id, sub["category_id"]),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_sub_del:"))
async def cb_adm_sub_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    sub_id = int(callback.data.split(":")[1])
    sub = await db.get_subcategory(sub_id)
    await callback.message.edit_text(
        "⚠️ Удалить раздел вместе со всеми товарами?",
        reply_markup=confirm_kb(f"adm_sub_del_ok:{sub_id}", f"adm_sub:{sub_id}")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_sub_del_ok:"))
async def cb_adm_sub_del_ok(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    sub_id = int(callback.data.split(":")[1])
    sub = await db.get_subcategory(sub_id)
    cat_id = sub["category_id"] if sub else 0
    await db.delete_subcategory(sub_id)
    await callback.answer("Удалено")
    if cat_id:
        subs = await db.get_subcategories(cat_id, only_visible=False)
        await callback.message.edit_text(
            "📂 Разделы",
            reply_markup=admin_subcategories_kb(subs, cat_id)
        )


# ─────────────────────────── Товары ───────────────────────────

@router.callback_query(F.data.startswith("adm_prods:"))
async def cb_adm_prods(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    sub_id = int(callback.data.split(":")[1])
    sub = await db.get_subcategory(sub_id)
    products = await db.get_products(sub_id, only_visible=False)
    cat_id = sub["category_id"] if sub else 0
    await callback.message.edit_text(
        f"🍬 Товары раздела «{sub['name'] if sub else '?'}»",
        reply_markup=admin_products_kb(products, sub_id, cat_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_prod_add:"))
async def cb_adm_prod_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    sub_id = int(callback.data.split(":")[1])
    await state.set_state(AdminProductStates.add_name)
    await state.update_data(subcategory_id=sub_id)
    await callback.message.edit_text(
        "Шаг 1/6. Введите <b>название</b> товара:",
        reply_markup=cancel_kb(f"adm_prods:{sub_id}"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminProductStates.add_name)
async def process_prod_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if not name or len(name) > 150:
        await message.answer("Название 1–150 символов:")
        return
    await state.update_data(name=name)
    await state.set_state(AdminProductStates.add_description)
    await message.answer("Шаг 2/6. Введите <b>описание</b> (или «-» чтобы пропустить):", parse_mode="HTML")


@router.message(AdminProductStates.add_description)
async def process_prod_desc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    desc = message.text.strip()
    if desc == "-":
        desc = ""
    await state.update_data(description=desc)
    await state.set_state(AdminProductStates.add_price)
    await message.answer("Шаг 3/6. Введите <b>цену</b> (число, например 250):", parse_mode="HTML")


@router.message(AdminProductStates.add_price)
async def process_prod_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        price = float(message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число:")
        return
    await state.update_data(price=price)
    await state.set_state(AdminProductStates.add_weight)
    await message.answer("Шаг 4/6. Введите <b>фасовку/вес</b> (например «150 г» или «-»):", parse_mode="HTML")


@router.message(AdminProductStates.add_weight)
async def process_prod_weight(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    weight = message.text.strip()
    if weight == "-":
        weight = ""
    await state.update_data(weight=weight)
    await state.set_state(AdminProductStates.add_photo)
    await message.answer(
        "Шаг 5/6. Пришлите <b>фото</b> товара (или отправьте «-» чтобы пропустить):",
        parse_mode="HTML"
    )


@router.message(AdminProductStates.add_photo, F.photo)
async def process_prod_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=file_id)
    await state.set_state(AdminProductStates.add_stock)
    await message.answer("Шаг 6/6. Введите <b>количество на складе</b> (целое число):", parse_mode="HTML")


@router.message(AdminProductStates.add_photo)
async def process_prod_photo_skip(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.strip() == "-":
        await state.update_data(photo_file_id=None)
        await state.set_state(AdminProductStates.add_stock)
        await message.answer("Шаг 6/6. Введите <b>количество на складе</b>:", parse_mode="HTML")
    else:
        await message.answer("Пришлите фото или «-» для пропуска:")


@router.message(AdminProductStates.add_stock)
async def process_prod_stock(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        stock = int(message.text.strip())
        if stock < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите целое неотрицательное число:")
        return
    data = await state.get_data()
    product_id = await db.add_product(
        subcategory_id=data["subcategory_id"],
        name=data["name"],
        description=data.get("description", ""),
        price=data["price"],
        weight=data.get("weight", ""),
        photo_file_id=data.get("photo_file_id"),
        stock=stock
    )
    await state.clear()
    await message.answer(
        f"✅ Товар «{data['name']}» добавлен (ID: {product_id})!",
        reply_markup=admin_main_kb()
    )


@router.callback_query(F.data.startswith("adm_prod:"))
async def cb_adm_prod(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    if len(parts) != 2:
        return
    product_id = int(parts[1])
    product = await db.get_product(product_id)
    if not product:
        await callback.answer("Не найдено", show_alert=True)
        return
    vis = "видим" if product["is_visible"] else "скрыт"
    text = (
        f"🍬 <b>{product['name']}</b>\n\n"
        f"{product['description'] or '—'}\n\n"
        f"Цена: {product['price']:.0f} ₽\n"
        f"Фасовка: {product['weight'] or '—'}\n"
        f"Остаток: {product['stock']}\n"
        f"Статус: {vis}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_product_actions_kb(product_id, product["subcategory_id"]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_pedit:"))
async def cb_adm_pedit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    # adm_pedit:ID:field
    parts = callback.data.split(":")
    product_id = int(parts[1])
    field = parts[2]
    await state.set_state(AdminProductStates.edit_value)
    await state.update_data(product_id=product_id, field=field)
    prompts = {
        "name": "Введите новое название:",
        "description": "Введите новое описание (или «-»):",
        "price": "Введите новую цену (число):",
        "weight": "Введите новую фасовку (или «-»):",
        "photo": "Пришлите новое фото (или «-» чтобы убрать):",
        "stock": "Введите новый остаток (целое число):",
    }
    await callback.message.edit_text(
        prompts.get(field, "Введите значение:"),
        reply_markup=cancel_kb(f"adm_prod:{product_id}")
    )
    await callback.answer()


@router.message(AdminProductStates.edit_value, F.photo)
async def process_edit_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    if data.get("field") != "photo":
        return
    file_id = message.photo[-1].file_id
    await db.update_product_field(data["product_id"], "photo_file_id", file_id)
    await state.clear()
    await message.answer("✅ Фото обновлено!", reply_markup=admin_main_kb())


@router.message(AdminProductStates.edit_value)
async def process_edit_value(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    field = data["field"]
    product_id = data["product_id"]
    text = message.text.strip() if message.text else ""

    try:
        if field == "name":
            if not text or len(text) > 150:
                raise ValueError("Название 1–150 символов")
            await db.update_product_field(product_id, "name", text)
        elif field == "description":
            val = "" if text == "-" else text
            await db.update_product_field(product_id, "description", val)
        elif field == "price":
            price = float(text.replace(",", "."))
            if price <= 0:
                raise ValueError("Цена должна быть > 0")
            await db.update_product_field(product_id, "price", price)
        elif field == "weight":
            val = "" if text == "-" else text
            await db.update_product_field(product_id, "weight", val)
        elif field == "photo":
            if text == "-":
                await db.update_product_field(product_id, "photo_file_id", None)
            else:
                await message.answer("Пришлите фото или «-»:")
                return
        elif field == "stock":
            stock = int(text)
            if stock < 0:
                raise ValueError("Остаток ≥ 0")
            await db.update_product_field(product_id, "stock", stock)
        else:
            raise ValueError("Неизвестное поле")
    except ValueError as e:
        await message.answer(f"Ошибка: {e}\nПопробуйте ещё раз:")
        return

    await state.clear()
    await message.answer("✅ Обновлено!", reply_markup=admin_main_kb())


@router.callback_query(F.data.startswith("adm_prod_vis:"))
async def cb_adm_prod_vis(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    product_id = int(callback.data.split(":")[1])
    new_vis = await db.toggle_product_visibility(product_id)
    await callback.answer("Показан" if new_vis else "Скрыт")
    product = await db.get_product(product_id)
    vis = "видим" if product["is_visible"] else "скрыт"
    text = (
        f"🍬 <b>{product['name']}</b>\n\n"
        f"Цена: {product['price']:.0f} ₽ | Остаток: {product['stock']}\n"
        f"Статус: {vis}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_product_actions_kb(product_id, product["subcategory_id"]),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_prod_del:"))
async def cb_adm_prod_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    product_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "⚠️ Удалить товар безвозвратно?",
        reply_markup=confirm_kb(f"adm_prod_del_ok:{product_id}", f"adm_prod:{product_id}")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_prod_del_ok:"))
async def cb_adm_prod_del_ok(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    product_id = int(callback.data.split(":")[1])
    product = await db.get_product(product_id)
    sub_id = product["subcategory_id"] if product else 0
    await db.delete_product(product_id)
    await callback.answer("Удалено")
    if sub_id:
        products = await db.get_products(sub_id, only_visible=False)
        sub = await db.get_subcategory(sub_id)
        cat_id = sub["category_id"] if sub else 0
        await callback.message.edit_text(
            "🍬 Товары",
            reply_markup=admin_products_kb(products, sub_id, cat_id)
        )


# ─────────────────────────── Заказы ───────────────────────────

@router.callback_query(F.data.startswith("adm_orders:"))
async def cb_adm_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    status = callback.data.split(":")[1]
    orders = await db.get_orders_by_status(status)
    status_label = db.STATUS_MAP.get(status, status)
    await callback.message.edit_text(
        f"📦 Заказы: {status_label}\n(показано до 50)",
        reply_markup=admin_orders_kb(orders, status)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ord:"))
async def cb_adm_ord(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    # adm_ord:ID  (не adm_ord_st)
    parts = callback.data.split(":")
    if len(parts) != 2:
        return
    order_id = int(parts[1])
    order = await db.get_order(order_id)
    if not order:
        await callback.answer("Не найдено", show_alert=True)
        return
    items = await db.get_order_items(order_id)
    user = await db.get_user(order["user_id"])
    uname = (user.get("username") or user.get("full_name") or str(order["user_id"])) if user else "?"
    items_text = "\n".join(
        f"• {i['name']} × {i['quantity']} = {i['price'] * i['quantity']:.0f} ₽"
        for i in items
    )
    status_text = db.STATUS_MAP.get(order["status"], order["status"])
    text = (
        f"📦 <b>Заказ #{order_id}</b>\n\n"
        f"Покупатель: @{uname} (ID: {order['user_id']})\n"
        f"Сумма: {order['total']:.0f} ₽\n"
        f"Статус: {status_text}\n"
        f"Создан: {order['created_at']}\n\n"
        f"{items_text}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_order_actions_kb(order_id, order["status"]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ord_st:"))
async def cb_adm_ord_st(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    order_id = int(parts[1])
    new_status = parts[2]
    order = await db.get_order(order_id)
    if not order:
        await callback.answer("Не найдено", show_alert=True)
        return
    await db.update_order_status(order_id, new_status)
    status_text = db.STATUS_MAP.get(new_status, new_status)
    await callback.answer(f"Статус: {status_text}")

    # Уведомление покупателю
    try:
        await bot.send_message(
            order["user_id"],
            f"📦 Статус вашего заказа <b>#{order_id}</b> изменён:\n\n{status_text}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning("Не удалось уведомить покупателя: %s", e)

    # Обновляем экран
    items = await db.get_order_items(order_id)
    user = await db.get_user(order["user_id"])
    uname = (user.get("username") or user.get("full_name") or str(order["user_id"])) if user else "?"
    items_text = "\n".join(
        f"• {i['name']} × {i['quantity']} = {i['price'] * i['quantity']:.0f} ₽"
        for i in items
    )
    text = (
        f"📦 <b>Заказ #{order_id}</b>\n\n"
        f"Покупатель: @{uname}\n"
        f"Сумма: {order['total']:.0f} ₽\n"
        f"Статус: {status_text}\n\n"
        f"{items_text}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_order_actions_kb(order_id, new_status),
        parse_mode="HTML"
    )


# ─────────────────────────── Заявки на пополнение ───────────────────────────

@router.callback_query(F.data == "adm_topups")
async def cb_adm_topups(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    topups = await db.get_pending_topups()
    if not topups:
        await callback.message.edit_text(
            "💳 Нет ожидающих заявок.",
            reply_markup=admin_topups_kb([])
        )
    else:
        await callback.message.edit_text(
            f"💳 Ожидающие заявки ({len(topups)}):",
            reply_markup=admin_topups_kb(topups)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_top:"))
async def cb_adm_top(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    # adm_top:ID
    parts = callback.data.split(":")
    if len(parts) != 2:
        return
    topup_id = int(parts[1])
    topup = await db.get_topup(topup_id)
    if not topup:
        await callback.answer("Не найдено", show_alert=True)
        return
    if topup["status"] != "pending":
        await callback.answer("Заявка уже обработана", show_alert=True)
        return
    user = await db.get_user(topup["user_id"])
    uname = (user.get("username") or user.get("full_name") or str(topup["user_id"])) if user else "?"
    caption = (
        f"💳 <b>Заявка #{topup_id}</b>\n\n"
        f"Пользователь: @{uname}\n"
        f"ID: <code>{topup['user_id']}</code>\n"
        f"Дата: {topup['created_at']}"
    )
    try:
        if topup["receipt_type"] == "photo":
            await callback.message.delete()
            await bot.send_photo(
                callback.from_user.id,
                photo=topup["receipt_file_id"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=admin_topup_actions_kb(topup_id)
            )
        else:
            await callback.message.delete()
            await bot.send_document(
                callback.from_user.id,
                document=topup["receipt_file_id"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=admin_topup_actions_kb(topup_id)
            )
    except Exception:
        await callback.message.edit_text(
            caption,
            reply_markup=admin_topup_actions_kb(topup_id),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_top_ok:"))
async def cb_adm_top_ok(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    topup_id = int(callback.data.split(":")[1])
    topup = await db.get_topup(topup_id)
    if not topup or topup["status"] != "pending":
        await callback.answer("Заявка уже обработана", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    await state.set_state(AdminTopupStates.waiting_amount)
    await state.update_data(topup_id=topup_id, topup_user_id=topup["user_id"])
    await callback.message.answer(
        f"Введите сумму для зачисления по заявке #{topup_id} (положительное число):",
        reply_markup=cancel_kb("adm_topups")
    )
    await callback.answer()


@router.message(AdminTopupStates.waiting_amount)
async def process_topup_amount(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число:")
        return

    data = await state.get_data()
    topup_id = data["topup_id"]
    user_id = data["topup_user_id"]

    ok = await db.process_topup(topup_id, "approved", message.from_user.id, amount)
    if not ok:
        await state.clear()
        await message.answer("⚠️ Заявка уже обработана другим администратором.")
        return

    new_bal = await db.change_balance(
        user_id, amount, "topup",
        f"Пополнение по заявке #{topup_id}", related_id=topup_id
    )
    await state.clear()
    await message.answer(
        f"✅ Зачислено {amount:.0f} ₽ пользователю {user_id}.\n"
        f"Новый баланс: {new_bal:.0f} ₽",
        reply_markup=admin_main_kb()
    )

    try:
        await bot.send_message(
            user_id,
            f"✅ Ваша заявка на пополнение <b>#{topup_id}</b> одобрена!\n\n"
            f"Зачислено: <b>{amount:.0f} ₽</b>\n"
            f"Текущий баланс: <b>{new_bal:.0f} ₽</b>\n\n"
            f"Спасибо! 🍬",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning("Не удалось уведомить пользователя: %s", e)


@router.callback_query(F.data.startswith("adm_top_no:"))
async def cb_adm_top_no(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    topup_id = int(callback.data.split(":")[1])
    topup = await db.get_topup(topup_id)
    if not topup or topup["status"] != "pending":
        await callback.answer("Заявка уже обработана", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    ok = await db.process_topup(topup_id, "rejected", callback.from_user.id)
    if not ok:
        await callback.answer("Уже обработана", show_alert=True)
        return

    await callback.answer("Отклонено")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    try:
        await bot.send_message(
            topup["user_id"],
            f"❌ Ваша заявка на пополнение <b>#{topup_id}</b> отклонена.\n\n"
            f"Если считаете, что произошла ошибка — напишите администратору.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning("Не удалось уведомить: %s", e)

    await callback.message.answer("Заявка отклонена.", reply_markup=admin_main_kb())


# ─────────────────────────── Настройки ───────────────────────────

@router.callback_query(F.data == "adm_settings")
async def cb_adm_settings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    wallet = await db.get_setting("wallet_address") or "(не задан)"
    await callback.message.edit_text(
        f"⚙️ <b>Настройки</b>\n\nТекущий кошелёк:\n<code>{wallet}</code>",
        reply_markup=admin_settings_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "adm_set_wallet")
async def cb_adm_set_wallet(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminSettingsStates.set_wallet)
    await callback.message.edit_text(
        "Введите адрес крипто-кошелька (или «-» чтобы очистить):",
        reply_markup=cancel_kb("adm_settings")
    )
    await callback.answer()


@router.message(AdminSettingsStates.set_wallet)
async def process_set_wallet(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    val = message.text.strip()
    if val == "-":
        val = ""
    await db.set_setting("wallet_address", val)
    await state.clear()
    await message.answer(
        f"✅ Адрес кошелька {'очищен' if not val else 'сохранён'}!",
        reply_markup=admin_main_kb()
    )


@router.callback_query(F.data == "adm_set_welcome")
async def cb_adm_set_welcome(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminSettingsStates.set_welcome)
    current = await db.get_setting("welcome_text")
    await callback.message.edit_text(
        f"Текущий текст приветствия:\n\n{current}\n\n"
        f"Введите новый текст:",
        reply_markup=cancel_kb("adm_settings")
    )
    await callback.answer()


@router.message(AdminSettingsStates.set_welcome)
async def process_set_welcome(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("welcome_text", message.text)
    await state.clear()
    await message.answer("✅ Текст приветствия обновлён!", reply_markup=admin_main_kb())


@router.callback_query(F.data == "adm_set_about")
async def cb_adm_set_about(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminSettingsStates.set_about)
    current = await db.get_setting("about_text")
    await callback.message.edit_text(
        f"Текущий текст «О магазине»:\n\n{current}\n\n"
        f"Введите новый текст:",
        reply_markup=cancel_kb("adm_settings")
    )
    await callback.answer()


@router.message(AdminSettingsStates.set_about)
async def process_set_about(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("about_text", message.text)
    await state.clear()
    await message.answer("✅ Текст «О магазине» обновлён!", reply_markup=admin_main_kb())


# ─────────────────────────── Пользователи ───────────────────────────

@router.callback_query(F.data == "adm_users")
async def cb_adm_users(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminUserStates.search)
    await callback.message.edit_text(
        "👤 Введите Telegram ID или username пользователя для поиска:",
        reply_markup=cancel_kb("admin_panel")
    )
    await callback.answer()


@router.message(AdminUserStates.search)
async def process_user_search(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    query = message.text.strip().lstrip("@")
    users = await db.search_users(query)
    await state.clear()
    if not users:
        await message.answer("Никого не найдено.", reply_markup=admin_main_kb())
        return
    if len(users) == 1:
        u = users[0]
        await message.answer(
            f"👤 <b>{u['full_name'] or '—'}</b>\n"
            f"Username: @{u['username'] or '—'}\n"
            f"ID: <code>{u['user_id']}</code>\n"
            f"Баланс: <b>{u['balance']:.0f} ₽</b>\n"
            f"Регистрация: {u['created_at']}",
            reply_markup=admin_user_kb(u["user_id"]),
            parse_mode="HTML"
        )
    else:
        lines = ["Найдено несколько пользователей:\n"]
        for u in users[:10]:
            lines.append(
                f"• {u['full_name'] or '—'} (@{u['username'] or '—'}) "
                f"ID:{u['user_id']} — {u['balance']:.0f} ₽"
            )
        lines.append("\nВведите точный ID для управления:")
        await state.set_state(AdminUserStates.search)
        await message.answer("\n".join(lines), reply_markup=cancel_kb("admin_panel"))


@router.callback_query(F.data.startswith("adm_ubal:"))
async def cb_adm_ubal(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    user_id = int(parts[1])
    action = parts[2]  # add / sub
    await state.set_state(AdminUserStates.change_balance)
    await state.update_data(target_user_id=user_id, action=action)
    verb = "начисления" if action == "add" else "списания"
    await callback.message.edit_text(
        f"Введите сумму для {verb} (положительное число):",
        reply_markup=cancel_kb("adm_users")
    )
    await callback.answer()


@router.message(AdminUserStates.change_balance)
async def process_change_balance(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число:")
        return

    data = await state.get_data()
    user_id = data["target_user_id"]
    action = data["action"]
    signed = amount if action == "add" else -amount
    typ = "admin_add" if action == "add" else "admin_sub"
    desc = f"Ручное {'начисление' if action == 'add' else 'списание'} администратором"

    new_bal = await db.change_balance(user_id, signed, typ, desc)
    await state.clear()
    await message.answer(
        f"✅ Баланс пользователя {user_id} изменён на {signed:+.0f} ₽.\n"
        f"Новый баланс: {new_bal:.0f} ₽",
        reply_markup=admin_main_kb()
    )
    try:
        await bot.send_message(
            user_id,
            f"💰 Ваш баланс изменён администратором: {signed:+.0f} ₽\n"
            f"Текущий баланс: <b>{new_bal:.0f} ₽</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


# ─────────────────────────── Рассылка ───────────────────────────

@router.callback_query(F.data == "adm_broadcast")
async def cb_adm_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminBroadcastStates.waiting_text)
    await callback.message.edit_text(
        "📢 Введите текст рассылки:",
        reply_markup=cancel_kb("admin_panel")
    )
    await callback.answer()


@router.message(AdminBroadcastStates.waiting_text)
async def process_broadcast_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(broadcast_text=message.text)
    await state.set_state(AdminBroadcastStates.waiting_photo)
    await message.answer(
        "Пришлите фото для рассылки (или отправьте «-» без фото):",
        reply_markup=cancel_kb("admin_panel")
    )


@router.message(AdminBroadcastStates.waiting_photo, F.photo)
async def process_broadcast_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(broadcast_photo=message.photo[-1].file_id)
    data = await state.get_data()
    await state.set_state(AdminBroadcastStates.confirm)
    await message.answer(
        f"📢 Предпросмотр:\n\n{data['broadcast_text']}\n\n"
        f"Отправить всем пользователям?",
        reply_markup=confirm_kb("adm_broadcast_go", "admin_panel")
    )


@router.message(AdminBroadcastStates.waiting_photo)
async def process_broadcast_no_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.strip() == "-":
        await state.update_data(broadcast_photo=None)
        data = await state.get_data()
        await state.set_state(AdminBroadcastStates.confirm)
        await message.answer(
            f"📢 Предпросмотр:\n\n{data['broadcast_text']}\n\n"
            f"Отправить всем пользователям?",
            reply_markup=confirm_kb("adm_broadcast_go", "admin_panel")
        )
    else:
        await message.answer("Пришлите фото или «-»:")


@router.callback_query(F.data == "adm_broadcast_go")
async def cb_adm_broadcast_go(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    photo = data.get("broadcast_photo")
    await state.clear()

    user_ids = await db.get_all_user_ids()
    success = 0
    fail = 0
    await callback.message.edit_text(f"📤 Рассылка начата ({len(user_ids)} получателей)...")

    for uid in user_ids:
        try:
            if photo:
                await bot.send_photo(uid, photo=photo, caption=text)
            else:
                await bot.send_message(uid, text)
            success += 1
        except Exception:
            fail += 1

    await callback.message.answer(
        f"✅ Рассылка завершена.\nУспешно: {success}\nОшибок: {fail}",
        reply_markup=admin_main_kb()
    )
    await callback.answer()
