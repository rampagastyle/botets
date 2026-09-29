"""
Хендлеры баланса и пополнения (пользовательская часть + обработка чеков).
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.fsm.context import FSMContext

import database as db
from keyboards import (
    balance_kb, topup_paid_kb, topup_cancel_kb, back_to_menu_kb,
    admin_topup_actions_kb
)
from states import TopupStates
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "balance")
async def cb_balance(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    bal = await db.get_balance(callback.from_user.id)
    await callback.message.edit_text(
        f"💰 <b>Ваш баланс:</b> {bal:.0f} ₽\n\n"
        f"Баланс можно пополнить переводом на крипто-кошелёк магазина.",
        reply_markup=balance_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "topup_start")
async def cb_topup_start(callback: CallbackQuery, state: FSMContext):
    wallet = await db.get_setting("wallet_address")
    if not wallet or not wallet.strip():
        await callback.message.edit_text(
            "😔 Пополнение временно недоступно.\n"
            "Администратор ещё не указал адрес кошелька.\n\n"
            "Попробуйте позже 🍬",
            reply_markup=back_to_menu_kb()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"💳 <b>Пополнение баланса</b>\n\n"
        f"Переведите любую сумму на кошелёк:\n\n"
        f"<code>{wallet}</code>\n\n"
        f"После перевода нажмите кнопку «Я оплатил(а)» и пришлите скриншот/чек.",
        reply_markup=topup_paid_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "topup_paid")
async def cb_topup_paid(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TopupStates.waiting_receipt)
    await callback.message.edit_text(
        "📎 Пришлите скриншот или документ с подтверждением перевода.\n\n"
        "(Только фото или файл — текст не принимается)",
        reply_markup=topup_cancel_kb()
    )
    await callback.answer()


@router.message(TopupStates.waiting_receipt, F.photo | F.document)
async def process_receipt(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    if message.photo:
        file_id = message.photo[-1].file_id
        receipt_type = "photo"
    else:
        file_id = message.document.file_id
        receipt_type = "document"

    topup_id = await db.create_topup(user_id, file_id, receipt_type)
    await state.clear()

    await message.answer(
        f"✅ Заявка <b>#{topup_id}</b> отправлена!\n\n"
        f"Ожидайте проверки администратором. "
        f"Мы сообщим, когда средства будут зачислены 🍬",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb()
    )

    # Уведомление всем админам
    user = await db.get_user(user_id)
    uname = message.from_user.username or message.from_user.full_name or str(user_id)
    caption = (
        f"💳 <b>Заявка на пополнение #{topup_id}</b>\n\n"
        f"Пользователь: @{uname}\n"
        f"ID: <code>{user_id}</code>\n"
        f"Дата: {message.date.strftime('%Y-%m-%d %H:%M')}"
    )
    for admin_id in ADMIN_IDS:
        try:
            if receipt_type == "photo":
                await bot.send_photo(
                    admin_id,
                    photo=file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=admin_topup_actions_kb(topup_id)
                )
            else:
                await bot.send_document(
                    admin_id,
                    document=file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=admin_topup_actions_kb(topup_id)
                )
        except Exception as e:
            logger.warning("Не удалось отправить заявку админу %s: %s", admin_id, e)


@router.message(TopupStates.waiting_receipt)
async def process_receipt_wrong(message: Message):
    await message.answer(
        "⚠️ Пожалуйста, пришлите именно <b>фото</b> или <b>документ</b> (скриншот перевода).\n"
        "Текстовые сообщения не принимаются.",
        parse_mode="HTML",
        reply_markup=topup_cancel_kb()
    )
