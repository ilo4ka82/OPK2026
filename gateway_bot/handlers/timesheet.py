"""
Обработчики табеля (используют database из Tabel_service на aiogram 2.x).
"""
import sys
import os
from datetime import datetime, timezone
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext

# ИСПРАВЛЕНО: Добавляем родительскую папку в sys.path (как в main.py)
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# ИСПРАВЛЕНО: Импортируем с полным путем пакета
from Tabel_service.database import (
    get_user,
    add_or_update_user,
    is_user_authorized,
    record_check_in,
    record_check_out,
)
from Tabel_service.utils import (
    is_within_office_zone,
    validate_location_age,
    TimesheetMessages,
    MAX_LOCATION_AGE_SECONDS,
)

from config import config
from keyboards import get_timesheet_menu, get_main_menu
from states import BotStates


async def timesheet_menu_handler(message: types.Message, state: FSMContext):
    """Обработчик меню табеля"""
    text = message.text
    user_id = message.from_user.id
    
    # Добавляем/обновляем пользователя в БД
    add_or_update_user(
        telegram_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Проверка авторизации
    if not is_user_authorized(user_id) and user_id not in config.ADMIN_USERS:
        await message.answer(
            "❌ Вы не авторизованы для использования табеля.\n"
            "Обратитесь к администратору.",
            reply_markup=get_main_menu()
        )
        await BotStates.main_menu.set()
        return
    
    if text == "▶️ Начать смену":
        # Запрашиваем геолокацию
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton("📍 Отправить геолокацию", request_location=True))
        keyboard.add(types.KeyboardButton("◀️ Главное меню"))
        
        await message.answer(
            "📍 Для отметки прихода отправьте вашу текущую геолокацию:",
            reply_markup=keyboard
        )
        await BotStates.timesheet_waiting_location.set()
    
    elif text == "⏹️ Закончить смену":
        success, message_text = record_check_out(user_id)
        await message.answer(message_text, reply_markup=get_timesheet_menu())
    
    elif text == "📊 Моя статистика":
        user_data = get_user(user_id)
        
        if user_data:
            full_name = user_data.get('application_full_name', 'Не указано')
            department = user_data.get('application_department', 'Не указан')
            
            await message.answer(
                f"📊 <b>Ваша статистика</b>\n\n"
                f"👤 ФИО: {full_name}\n"
                f"🏢 Сектор: {department}\n\n"
                f"<i>Детальная статистика в разработке...</i>",
                parse_mode="HTML",
                reply_markup=get_timesheet_menu()
            )
        else:
            await message.answer(
                "❌ Данные не найдены",
                reply_markup=get_timesheet_menu()
            )
    
    elif text == "◀️ Главное меню":
        await message.answer(
            "🏠 Главное меню",
            reply_markup=get_main_menu()
        )
        await BotStates.main_menu.set()
    
    else:
        await message.answer(
            "❓ Используйте кнопки меню",
            reply_markup=get_timesheet_menu()
        )


async def location_handler(message: types.Message, state: FSMContext):
    """Обработчик получения геолокации для отметки прихода"""
    user_id = message.from_user.id
    
    # Проверка на пересылку
    if message.forward_from or message.forward_from_chat:
        await message.answer(
            TimesheetMessages.CHECKIN_FORWARDED,
            reply_markup=get_timesheet_menu()
        )
        await BotStates.timesheet_menu.set()
        return
    
    # Проверка возраста геолокации
    message_date = message.date
    if not message_date.tzinfo:
        message_date = message_date.replace(tzinfo=timezone.utc)
    
    is_valid_age, age_seconds = validate_location_age(
        message_date, 
        MAX_LOCATION_AGE_SECONDS
    )
    
    if not is_valid_age:
        await message.answer(
            TimesheetMessages.CHECKIN_OLD_LOCATION.format(age=age_seconds),
            reply_markup=get_timesheet_menu()
        )
        await BotStates.timesheet_menu.set()
        return
    
    # Получаем координаты
    location = message.location
    latitude = location.latitude
    longitude = location.longitude
    
    # Проверяем геозону
    if is_within_office_zone(latitude, longitude):
        success, message_text = record_check_in(user_id, latitude, longitude)
        await message.answer(message_text, reply_markup=get_timesheet_menu())
    else:
        await message.answer(
            TimesheetMessages.CHECKIN_OUTSIDE_ZONE,
            reply_markup=get_timesheet_menu()
        )
    
    await BotStates.timesheet_menu.set()


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков табеля"""
    
    # Меню табеля
    dp.register_message_handler(
        timesheet_menu_handler,
        state=BotStates.timesheet_menu
    )
    
    # Получение геолокации
    dp.register_message_handler(
        location_handler,
        content_types=types.ContentType.LOCATION,
        state=BotStates.timesheet_waiting_location
    )