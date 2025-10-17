"""
Состояния FSM для табеля.
"""
from aiogram.dispatcher.filters.state import State, StatesGroup


class ApplicationStates(StatesGroup):
    """Состояния для подачи заявки на доступ."""
    ASK_FULL_NAME = State()
    ASK_DEPARTMENT = State()


class ManualCheckinStates(StatesGroup):
    """Состояния для ручной заявки на отметку."""
    REQUEST_TIME = State()


class AdminManualCheckinStates(StatesGroup):
    """Состояния для админа при обработке ручных заявок."""
    LIST_REQUESTS = State()
    PROCESS_SINGLE = State()
    ENTER_NEW_TIME = State()
    CONFIRM_DECISION = State()


class ExportStates(StatesGroup):
    """Состояния для экспорта отчетов."""
    SELECT_SECTOR = State()
    SELECT_PERIOD = State()
    GET_START_DATE = State()
    GET_END_DATE = State()
    CONFIRM_EXPORT = State()


class EditCheckoutStates(StatesGroup):
    """Состояния для редактирования времени ухода."""
    AWAIT_NAME = State()
    SELECT_USER = State()
    SELECT_PERIOD = State()
    SELECT_SESSION = State()
    AWAIT_NEW_TIME = State()
    CONFIRM = State()