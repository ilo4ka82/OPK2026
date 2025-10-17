"""
Главный файл запуска бота табеля.
"""
import logging
import sys
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from .config import TimesheetConfig
from .database import init_db
from .handlers import (
    application_conv_handler,
    checkin_command,
    checkout_command,
    location_handler,
    manual_checkin_conv_handler,
)
from .handlers.admin import (
    admin_authorize_command,
    on_shift_command,
    on_shift_button_press,
    admin_pending_users_command,
    admin_action_callback_handler,
    admin_manual_checkins_conv_handler,
    export_conv_handler,
    edit_checkout_conv_handler,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("tabel_bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Уменьшаем уровень логирования для библиотеки httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def start_command(update, context):
    """
    Команда /start для табеля.
    Проверяет авторизацию и показывает инструкции.
    """
    from .database import get_user, add_or_update_user, is_user_authorized
    from .utils import TimesheetMessages
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    user = update.effective_user
    user_id = user.id
    
    # Добавляем/обновляем пользователя в БД
    add_or_update_user(
        telegram_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    user_data = get_user(user_id)
    is_admin = TimesheetConfig.is_admin(user_id)
    
    # Проверяем статус пользователя
    if is_admin or is_user_authorized(user_id):
        status = "✅ Авторизован (Администратор)" if is_admin else "✅ Авторизован"
        
        welcome_message = TimesheetMessages.WELCOME_AUTHORIZED.format(
            name=user.first_name or "Пользователь",
            user_id=user_id,
            status=status
        )
        
        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown'
        )
        
        # Показываем доступные команды
        commands_text = (
            "📋 **Доступные команды:**\n\n"
            "👤 **Для пользователей:**\n"
            "/checkin - Отметить приход\n"
            "/checkout - Отметить уход\n"
            "/request_manual_checkin - Запросить ручную отметку\n\n"
        )
        
        if is_admin:
            commands_text += (
                "👑 **Для администраторов:**\n"
                "/admin_pending_users - Список заявок на доступ\n"
                "/admin_authorize USER_ID - Авторизовать пользователя\n"
                "/admin_manual_checkins - Обработать ручные заявки\n"
                "/on_shift - Кто на смене\n"
                "/export_attendance - Экспорт посещаемости\n"
                "/edit_checkout - Редактировать время ухода\n"
            )
        
        await update.message.reply_text(commands_text, parse_mode='Markdown')
        
    elif user_data and user_data.get('application_status') == 'pending':
        welcome_message = TimesheetMessages.WELCOME_PENDING.format(
            name=user.first_name or "Пользователь"
        )
        await update.message.reply_text(welcome_message)
        
    else:
        welcome_message = TimesheetMessages.WELCOME_NEW.format(
            name=user.first_name or "Пользователь"
        )
        
        keyboard = [
            [InlineKeyboardButton("📝 Подать заявку на доступ", callback_data="apply_for_access")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup
        )


async def help_command(update, context):
    """Команда /help - показывает список команд."""
    from .database import is_user_authorized
    
    user_id = update.effective_user.id
    is_admin = TimesheetConfig.is_admin(user_id)
    is_authorized = is_user_authorized(user_id)
    
    if not (is_admin or is_authorized):
        await update.message.reply_text(
            "Вы не авторизованы. Пожалуйста, используйте /start для подачи заявки."
        )
        return
    
    help_text = (
        "📋 **Справка по командам табеля:**\n\n"
        "👤 **Основные команды:**\n"
        "/start - Начать работу\n"
        "/help - Показать эту справку\n"
        "/checkin - Отметить приход (требуется геолокация)\n"
        "/checkout - Отметить уход\n"
        "/request_manual_checkin - Запросить ручную отметку прихода\n\n"
    )
    
    if is_admin:
        help_text += (
            "👑 **Команды администратора:**\n"
            "/admin_pending_users - Список ожидающих авторизации\n"
            "/admin_authorize USER_ID - Авторизовать пользователя по ID\n"
            "/admin_manual_checkins - Обработать заявки на ручную отметку\n"
            "/on_shift - Посмотреть кто на смене\n"
            "/export_attendance - Экспортировать данные в Excel\n"
            "/edit_checkout - Редактировать время ухода сотрудника\n"
        )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')


def main():
    """Запуск бота."""
    try:
        # Инициализация базы данных
        logger.info("Инициализация базы данных...")
        init_db()
        logger.info("База данных успешно инициализирована.")
        
        # Создание приложения
        logger.info("Создание Telegram приложения...")
        application = Application.builder().token(TimesheetConfig.TELEGRAM_BOT_TOKEN).build()
        
        # === БАЗОВЫЕ КОМАНДЫ ===
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        
        # === ПОЛЬЗОВАТЕЛЬСКИЕ ОБРАБОТЧИКИ ===
        application.add_handler(CommandHandler("checkin", checkin_command))
        application.add_handler(CommandHandler("checkout", checkout_command))
        application.add_handler(MessageHandler(filters.LOCATION, location_handler))
        
        # === CONVERSATION HANDLERS ===
        application.add_handler(application_conv_handler)
        application.add_handler(manual_checkin_conv_handler)
        
        # === АДМИНСКИЕ КОМАНДЫ ===
        application.add_handler(CommandHandler("admin_authorize", admin_authorize_command))
        application.add_handler(CommandHandler("on_shift", on_shift_command))
        application.add_handler(CommandHandler("admin_pending_users", admin_pending_users_command))
        
        # === АДМИНСКИЕ CONVERSATION HANDLERS ===
        application.add_handler(admin_manual_checkins_conv_handler)
        application.add_handler(export_conv_handler)
        application.add_handler(edit_checkout_conv_handler)
        
        # === CALLBACK HANDLERS ===
        application.add_handler(CallbackQueryHandler(on_shift_button_press, pattern="^on_shift_"))
        application.add_handler(CallbackQueryHandler(admin_action_callback_handler, pattern="^(authorize_user|reject_user|paginate_list):"))
        
        logger.info("✅ Все обработчики успешно зарегистрированы.")
        
        # Запуск бота
        logger.info("🚀 Запуск бота табеля...")
        application.run_polling(allowed_updates=["message", "callback_query"])
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
