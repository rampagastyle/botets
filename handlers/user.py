"""
Пользовательские хендлеры: старт, каталог, корзина, заказы, о магазине.
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

import database as db
from keyboards import (
    main_menu_kb, categories_kb, subcategories_kb, products_kb,
    product_card_kb, cart_kb, my_orders_kb, back_to_menu_kb,
    insufficient_balance_kb
)
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await db.ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name or ""
    )
    welcome = await db.get_setting("welcome_text")
    await message.answer(welcome, reply_markup=main_menu_kb())


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    welcome = await db.get_setting("welcome_text")
    try:
        await callback.message.edit_text(welcome, reply_markup=main_menu_kb())
    except Exception:
        await callback.message.answer(welcome, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "about")
async def cb_about(callback: CallbackQuery):
    text = await db.get_setting("about_text")
    await callback.message.edit_text(text, reply_markup=back_to_menu_kb())
    await callback.answer()


# ─────────────────────────── Каталог ───────────────────────────

@router.callback_query(F.data == "catalog")
async def cb_catalog(callback: CallbackQuery):
    cats = await db.get_categories(only_visible=True)
    if not cats:
        await callback.message.edit_text(
            "🛍 Каталог пока пуст. Загляните позже 🍬",
            reply_markup=back_to_menu_kb()
        )
    else:
        await callback.message.edit_text(
            "🛍 Выберите категорию:",
            reply_markup=categories_kb(cats)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def cb_category(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    cat = await db.get_category(cat_id)
    if not cat or not cat["is_visible"]:
        await callback.answer("Категория недоступна", show_alert=True)
        return
    subs = await db.get_subcategories(cat_id, only_visible=True)
    if not subs:
        await callback.message.edit_text(
            f"📂 {cat['name']}\n\nРазделов пока нет.",
            reply_markup=subcategories_kb([], cat_id)
        )
    else:
        await callback.message.edit_text(
            f"📂 {cat['name']}\n\nВыберите раздел:",
            reply_markup=subcategories_kb(subs, cat_id)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:"))
async def cb_subcategory(callback: CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    sub = await db.get_subcategory(sub_id)
    if not sub or not sub["is_visible"]:
        await callback.answer("Раздел недоступен", show_alert=True)
        return
    products = await db.get_products(sub_id, only_visible=True)
    cat_id = sub["category_id"]
    if not products:
        await callback.message.edit_text(
            f"🍬 {sub['name']}\n\nТоваров пока нет.",
            reply_markup=products_kb([], sub_id, cat_id)
        )
    else:
        await callback.message.edit_text(
            f"🍬 {sub['name']}\n\nВыберите товар:",
            reply_markup=products_kb(products, sub_id, cat_id)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("prod:"))
async def cb_product(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    product = await db.get_product(product_id)
    if not product or not product["is_visible"]:
        await callback.answer("Товар недоступен", show_alert=True)
        return
    sub = await db.get_subcategory(product["subcategory_id"])
    text = (
        f"<b>{product['name']}</b>\n\n"
        f"{product['description'] or 'Вкусный домашний мармелад 🍬'}\n\n"
        f"💰 Цена: <b>{product['price']:.0f} ₽</b>\n"
        f"⚖️ Фасовка: {product['weight'] or '—'}\n"
        f"📦 В наличии: {product['stock']} шт."
    )
    kb = product_card_kb(product_id, product["subcategory_id"])
    try:
        if product["photo_file_id"]:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=product["photo_file_id"],
                caption=text,
                reply_markup=kb,
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logger.warning("Ошибка показа товара: %s", e)
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("add_cart:"))
async def cb_add_to_cart(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    product = await db.get_product(product_id)
    if not product or not product["is_visible"]:
        await callback.answer("Товар недоступен", show_alert=True)
        return
    if product["stock"] <= 0:
        await callback.answer("К сожалению, товар закончился 😔", show_alert=True)
        return
    await db.add_to_cart(callback.from_user.id, product_id, 1)
    await callback.answer("✅ Добавлено в корзину!", show_alert=False)


# ─────────────────────────── Корзина ───────────────────────────

@router.callback_query(F.data == "cart")
async def cb_cart(callback: CallbackQuery):
    items = await db.get_cart(callback.from_user.id)
    if not items:
        await callback.message.edit_text(
            "🛒 Корзина пуста.\n\nЗагляните в каталог и выберите что-нибудь вкусное! 🍬",
            reply_markup=cart_kb([])
        )
    else:
        lines = ["🛒 <b>Ваша корзина:</b>\n"]
        total = 0.0
        for item in items:
            subtotal = item["price"] * item["quantity"]
            total += subtotal
            lines.append(
                f"• {item['name']} × {item['quantity']} = {subtotal:.0f} ₽"
            )
        lines.append(f"\n<b>Итого: {total:.0f} ₽</b>")
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=cart_kb(items),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("cart_plus:"))
async def cb_cart_plus(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    items = await db.get_cart(callback.from_user.id)
    current = next((i for i in items if i["product_id"] == product_id), None)
    if not current:
        await callback.answer("Товар не найден в корзине")
        return
    product = await db.get_product(product_id)
    if product and current["quantity"] >= product["stock"]:
        await callback.answer(f"Максимум на складе: {product['stock']}", show_alert=True)
        return
    await db.set_cart_quantity(callback.from_user.id, product_id, current["quantity"] + 1)
    # Обновляем корзину
    await cb_cart(callback)


@router.callback_query(F.data.startswith("cart_minus:"))
async def cb_cart_minus(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    items = await db.get_cart(callback.from_user.id)
    current = next((i for i in items if i["product_id"] == product_id), None)
    if not current:
        await callback.answer("Товар не найден в корзине")
        return
    new_qty = current["quantity"] - 1
    await db.set_cart_quantity(callback.from_user.id, product_id, new_qty)
    await cb_cart(callback)


@router.callback_query(F.data.startswith("cart_del:"))
async def cb_cart_del(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    await db.remove_from_cart(callback.from_user.id, product_id)
    await callback.answer("Удалено из корзины")
    await cb_cart(callback)


@router.callback_query(F.data == "checkout")
async def cb_checkout(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    items = await db.get_cart(user_id)
    if not items:
        await callback.answer("Корзина пуста", show_alert=True)
        return

    total = sum(i["price"] * i["quantity"] for i in items)
    balance = await db.get_balance(user_id)

    if balance < total:
        await callback.message.edit_text(
            f"😔 Недостаточно средств.\n\n"
            f"Сумма заказа: <b>{total:.0f} ₽</b>\n"
            f"Ваш баланс: <b>{balance:.0f} ₽</b>\n\n"
            f"Пополните баланс, чтобы оформить заказ.",
            reply_markup=insufficient_balance_kb(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    # Проверяем остатки
    for item in items:
        product = await db.get_product(item["product_id"])
        if not product or product["stock"] < item["quantity"]:
            await callback.answer(
                f"Недостаточно «{item['name']}» на складе",
                show_alert=True
            )
            return

    # Создаём заказ, списываем баланс, очищаем корзину
    order_id = await db.create_order(user_id, items)
    await db.change_balance(
        user_id, -total, "order",
        f"Оплата заказа #{order_id}", related_id=order_id
    )
    await db.clear_cart(user_id)

    await callback.message.edit_text(
        f"✅ Заказ <b>#{order_id}</b> оформлен!\n\n"
        f"Сумма: {total:.0f} ₽\n"
        f"Статус: 🆕 Новый\n\n"
        f"Мы уже готовим ваш мармелад 🍬\n"
        f"Следить за статусом можно в разделе «Мои заказы».",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

    # Уведомление админам
    user = await db.get_user(user_id)
    uname = user.get("username") or user.get("full_name") or str(user_id)
    order_items = await db.get_order_items(order_id)
    items_text = "\n".join(
        f"• {i['name']} × {i['quantity']} = {i['price'] * i['quantity']:.0f} ₽"
        for i in order_items
    )
    notify = (
        f"🆕 <b>Новый заказ #{order_id}</b>\n\n"
        f"Покупатель: @{uname} (ID: {user_id})\n"
        f"Сумма: {total:.0f} ₽\n\n"
        f"{items_text}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, notify, parse_mode="HTML")
        except Exception as e:
            logger.warning("Не удалось уведомить админа %s: %s", admin_id, e)


# ─────────────────────────── Мои заказы ───────────────────────────

@router.callback_query(F.data == "my_orders")
async def cb_my_orders(callback: CallbackQuery):
    orders = await db.get_user_orders(callback.from_user.id)
    if not orders:
        await callback.message.edit_text(
            "📦 У вас пока нет заказов.\n\nСамое время выбрать вкусный мармелад! 🍬",
            reply_markup=my_orders_kb()
        )
    else:
        lines = ["📦 <b>Ваши заказы:</b>\n"]
        for o in orders:
            status_text = db.STATUS_MAP.get(o["status"], o["status"])
            lines.append(
                f"#{o['id']} — {o['total']:.0f} ₽ — {status_text}\n"
                f"   {o['created_at'][:16]}"
            )
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=my_orders_kb(),
            parse_mode="HTML"
        )
    await callback.answer()
