"""
Обработчик ручной заявки на отметку прихода от пользователя.
"""
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode
import pytz

from ..database import add_manual_checkin_request, is_user_authorized
from ..utils import (
    validate_datetime_format,
    TimesheetMessages,
    AdminMessages,
    escape_markdown_v2,
)
from ..states import ManualCheckinStates
from ..config import TimesheetConfig

logger = logging.getLogger(__name__)
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


async def request_manual_checkin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог запроса ручной отметки прихода."""
    user = update.effective_user
    logger.info(f"User {user.id} инициировал запрос на ручную отметку прихода.")
    
    if not is_user_authorized(user.id):
        await update.message.reply_text("Эта функция доступна только для авторизованных пользователей.")
        return ConversationHandler.END

    await update.message.reply_text(TimesheetMessages.MANUAL_REQUEST_PROMPT)
    return ManualCheckinStates.REQUEST_TIME


async def process_manual_checkin_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает введенное время для ручной отметки."""
    user = update.effective_user
    user_input_time_str = update.message.text
    
    # Валидация формата
    is_valid, dt_obj, error_msg = validate_datetime_format(user_input_time_str, '%d.%m.%Y %H:%M')
    
    if not is_valid:
        await update.message.reply_text(TimesheetMessages.MANUAL_REQUEST_INVALID_FORMAT)
        return ManualCheckinStates.REQUEST_TIME
    
    try:
        # Создаем московское время из введенных данных
        moscow_dt = MOSCOW_TZ.localize(dt_obj)
        
        # Сохраняем в базу
        success = add_manual_checkin_request(user_id=user.id, requested_checkin_time=moscow_dt)
        
        if success:
            time_str = moscow_dt.strftime('%d.%m.%Y %H:%M')
            await update.message.reply_text(
                TimesheetMessages.MANUAL_REQUEST_SUBMITTED.format(time=time_str)
            )
            logger.info(f"User {user.id} успешно подал заявку на ручную отметку на {time_str} (MSK).")
            
            # Уведомление администраторам (будет в admin/manual_requests.py)
            # TODO: вызвать функцию уведомления
            
        else:
            await update.message.reply_text(TimesheetMessages.ERROR_DB)
            logger.error(f"Не удалось сохранить заявку для user {user.id}.")
            
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка в process_manual_checkin_time для user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(TimesheetMessages.ERROR_UNKNOWN)
        return ConversationHandler.END


async def cancel_manual_checkin_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет диалог запроса ручной отметки."""
    user = update.effective_user
    await update.message.reply_text("Запрос на ручную отметку прихода отменен.")
    logger.info(f"User {user.id} отменил диалог запроса ручной отметки.")
    context.user_data.clear()
    return ConversationHandler.END


# ConversationHandler для ручной заявки
manual_checkin_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("request_manual_checkin", request_manual_checkin_start)
    ],
    states={
        ManualCheckinStates.REQUEST_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_manual_checkin_time)
        ],
    },
    fallbacks=[
        CommandHandler("cancel_manual_checkin", cancel_manual_checkin_dialog)
    ],
    name="manual_checkin_request_flow",
    per_user=True,
    per_chat=True,
    allow_reentry=True
)
