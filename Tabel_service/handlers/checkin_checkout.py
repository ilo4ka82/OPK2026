"""
Обработчики отметок прихода и ухода.
"""
import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ..database import (
    get_user,
    add_or_update_user,
    is_user_authorized,
    record_check_in,
    record_check_out,
)
from ..utils import (
    escape_markdown_v2,
    is_within_office_zone,
    validate_location_age,
    TimesheetMessages,
    MAX_LOCATION_AGE_SECONDS,
)
from ..keyboards import get_location_keyboard, remove_keyboard
from ..config import TimesheetConfig

logger = logging.getLogger(__name__)


async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /checkin - запрашивает геолокацию для отметки прихода."""
    user = update.effective_user
    user_data_from_db = get_user(user.id)
    is_admin_from_config = TimesheetConfig.is_admin(user.id)
    is_authorized_in_db = user_data_from_db and user_data_from_db['is_authorized']
    
    if not (is_admin_from_config or is_authorized_in_db):
        error_message = escape_markdown_v2(TimesheetMessages.ERROR_NOT_AUTHORIZED)
        await update.message.reply_text(error_message, parse_mode=ParseMode.MARKDOWN_V2)
        logger.warning(f"Неавторизованная попытка /checkin от {user.id} ({user.username})")
        return
    
    if is_admin_from_config and (not user_data_from_db or not is_authorized_in_db):
        add_or_update_user(user.id, user.username, user.first_name, user.last_name)
        # Админа авторизуем автоматически (можно добавить функцию в database)
        logger.info(f"Администратор {user.id} ({user.username}) автоматически добавлен при /checkin.")
    
    await update.message.reply_text(
        escape_markdown_v2(TimesheetMessages.CHECKIN_REQUEST_LOCATION),
        reply_markup=get_location_keyboard(),
        parse_mode=ParseMode.MARKDOWN_V2
    )


async def checkout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /checkout - отметка ухода."""
    user = update.effective_user
    user_data_from_db = get_user(user.id)
    is_admin_from_config = TimesheetConfig.is_admin(user.id)
    is_authorized_in_db = user_data_from_db and user_data_from_db['is_authorized']
    
    if not (is_admin_from_config or is_authorized_in_db):
        error_message = escape_markdown_v2(TimesheetMessages.ERROR_NOT_AUTHORIZED)
        await update.message.reply_text(error_message, parse_mode=ParseMode.MARKDOWN_V2)
        logger.warning(f"Неавторизованная попытка /checkout от {user.id} ({user.username})")
        return
    
    if is_admin_from_config and (not user_data_from_db or not is_authorized_in_db):
        add_or_update_user(user.id, user.username, user.first_name, user.last_name)
        logger.info(f"Администратор {user.id} ({user.username}) автоматически добавлен при /checkout.")
    
    success, message_from_db = record_check_out(user.id)
    await update.message.reply_text(
        escape_markdown_v2(message_from_db),
        parse_mode=ParseMode.MARKDOWN_V2
    )


async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает полученную геолокацию для отметки прихода."""
    user = update.effective_user
    message = update.message

    if not message or not message.location:
        logger.warning(f"location_handler вызван без location для {user.id}")
        return

    # ФИЛЬТР №1: Проверка на пересылку
    if message.forward_origin:
        logger.warning(f"Пользователь {user.id} попытался переслать геолокацию.")
        await message.reply_text(
            escape_markdown_v2(TimesheetMessages.CHECKIN_FORWARDED),
            reply_markup=remove_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    # ФИЛЬТР №2: Проверка на "свежесть"
    message_date = message.date
    is_valid_age, age_seconds = validate_location_age(message_date, MAX_LOCATION_AGE_SECONDS)
    
    if not is_valid_age:
        logger.critical(
            f"ОТКЛОНЕНА СТАРАЯ ГЕОЛОКАЦИЯ ОТ {user.id}. "
            f"Возраст: {age_seconds} сек."
        )
        await message.reply_text(
            escape_markdown_v2(TimesheetMessages.CHECKIN_OLD_LOCATION.format(age=age_seconds)),
            reply_markup=remove_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
        
    location = message.location
    latitude = location.latitude
    longitude = location.longitude

    logger.info(f"Получена геолокация от {user.id}: Широта={latitude}, Долгота={longitude}")

    user_data_from_db = get_user(user.id)
    is_admin_from_config = TimesheetConfig.is_admin(user.id)
    is_authorized_in_db = user_data_from_db and user_data_from_db.get('is_authorized')

    if not (is_admin_from_config or is_authorized_in_db):
        error_message_unauth = escape_markdown_v2(TimesheetMessages.ERROR_NOT_AUTHORIZED)
        await message.reply_text(error_message_unauth, parse_mode=ParseMode.MARKDOWN_V2)
        logger.warning(f"Неавторизованная попытка отправки геолокации от {user.id}")
        await message.reply_text(
            escape_markdown_v2("Пожалуйста, обратитесь к администратору для авторизации."),
            reply_markup=remove_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    if is_admin_from_config and (not user_data_from_db or not is_authorized_in_db):
        add_or_update_user(user.id, user.username or "N/A", user.first_name or "N/A", user.last_name or "N/A")
        logger.info(f"Администратор {user.id} автоматически добавлен при отправке локации.")

    if is_within_office_zone(latitude, longitude):
        logger.info(f"Пользователь {user.id} в разрешенной геозоне. Попытка check-in.")
        success, message_from_db = record_check_in(user.id, latitude, longitude)
        
        await message.reply_text(
            escape_markdown_v2(message_from_db),
            reply_markup=remove_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        logger.info(f"Пользователь {user.id} вне разрешенной геозоны. Check-in отклонен.")
        error_message_geofence = escape_markdown_v2(TimesheetMessages.CHECKIN_OUTSIDE_ZONE)
        await message.reply_text(
            error_message_geofence,
            reply_markup=remove_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2
        )