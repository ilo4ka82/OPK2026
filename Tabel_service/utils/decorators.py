"""
Декораторы для обработчиков табеля.
"""
from functools import wraps
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from .formatters import escape_markdown_v2

logger = logging.getLogger(__name__)


def admin_required(func):
    """
    Декоратор для проверки прав администратора.
    
    Usage:
        @admin_required
        async def my_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            ...
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        # Импортируем здесь, чтобы избежать циклических импортов
        from ..config import TimesheetConfig
        
        if user_id not in TimesheetConfig.ADMIN_TELEGRAM_IDS:
            error_message = escape_markdown_v2(
                "❌ Эта команда доступна только администратору."
            )
            
            if update.message:
                await update.message.reply_text(
                    error_message, 
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            
            logger.warning(
                f"Несанкционированный доступ к админ-команде {func.__name__} "
                f"от {user_id} ({update.effective_user.username})"
            )
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


def log_errors(func):
    """
    Декоратор для логирования ошибок в обработчиках.
    
    Usage:
        @log_errors
        async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            ...
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(
                f"Ошибка в {func.__name__}: {e}",
                exc_info=True,
                extra={
                    'user_id': update.effective_user.id if update.effective_user else None,
                    'chat_id': update.effective_chat.id if update.effective_chat else None
                }
            )
            
            # Уведомляем пользователя об ошибке
            if update.effective_message:
                await update.effective_message.reply_text(
                    "❌ Произошла ошибка при обработке команды. "
                    "Пожалуйста, попробуйте позже или обратитесь к администратору."
                )
            
            raise
    
    return wrapper