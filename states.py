from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    """Состояния оформления заказа (если понадобится расширение)."""
    confirm = State()


class TopupStates(StatesGroup):
    """Состояния пополнения баланса пользователем."""
    waiting_receipt = State()


class AdminTopupStates(StatesGroup):
    """Админ вводит сумму для одобрения заявки."""
    waiting_amount = State()


class AdminCategoryStates(StatesGroup):
    """Управление категориями."""
    add_name = State()
    rename = State()


class AdminSubcategoryStates(StatesGroup):
    """Управление разделами (подкатегориями)."""
    add_name = State()
    rename = State()


class AdminProductStates(StatesGroup):
    """Пошаговое добавление / редактирование товара."""
    add_subcategory = State()
    add_name = State()
    add_description = State()
    add_price = State()
    add_weight = State()
    add_photo = State()
    add_stock = State()
    edit_field = State()
    edit_value = State()
    change_stock = State()


class AdminOrderStates(StatesGroup):
    """Смена статуса заказа."""
    change_status = State()


class AdminSettingsStates(StatesGroup):
    """Настройки магазина."""
    set_wallet = State()
    set_welcome = State()
    set_about = State()


class AdminUserStates(StatesGroup):
    """Работа с пользователями."""
    search = State()
    change_balance = State()


class AdminBroadcastStates(StatesGroup):
    """Рассылка."""
    waiting_text = State()
    waiting_photo = State()
    confirm = State()
