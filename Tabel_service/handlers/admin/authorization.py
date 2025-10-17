"""
Обработчик авторизации пользователей администратором.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ...database import authorize_user, get_user
from ...utils import escape_markdown_v2, admin_required, AdminMessages
from ...config import TimesheetConfig

logger = logging.getLogger(__name__)


@admin_required
async def admin_authorize_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда /admin_authorize - авторизует пользователя по ID.
    
    Usage: /admin_authorize USER_ID
    """
    admin_user = update.effective_user
    
    if not context.args:
        text_to_send = "Пожалуйста, укажите Telegram ID пользователя\\.\nИспользование: /admin\\_authorize `USER_ID`"
        await update.message.reply_text(text_to_send, parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    try:
        user_id_to_authorize = int(context.args[0])
        success, message_from_db = authorize_user(user_id_to_authorize, admin_user.id)
        
        await update.message.reply_text(
            escape_markdown_v2(message_from_db),
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
        if success and "успешно авторизован" in message_from_db:
            target_user_info = get_user(user_id_to_authorize)
            if target_user_info:
                try:
                    await context.bot.send_message(
                        chat_id=user_id_to_authorize,
                        text="🎉 Поздравляем! Администратор подтвердил вашу авторизацию. Теперь вы можете использовать все функции бота."
                    )
                    logger.info(f"Уведомление об авторизации отправлено пользователю {user_id_to_authorize}")
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление пользователю {user_id_to_authorize}: {e}")
            else:
                logger.warning(f"Не удалось получить данные пользователя {user_id_to_authorize} для отправки уведомления.")
                
    except ValueError:
        text_to_send = "Telegram ID должен быть числом\\.\nИспользование: /admin\\_authorize `USER_ID`"
        await update.message.reply_text(text_to_send, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        logger.error(f"Ошибка в admin_authorize_command: {e}", exc_info=True)
        await update.message.reply_text(
            escape_markdown_v2("Произошла непредвиденная ошибка при авторизации."),
            parse_mode=ParseMode.MARKDOWN_V2
        )