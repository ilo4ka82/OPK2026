"""
Обработчик подачи заявки на доступ к табелю.
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from ..database import submit_application, get_user
from ..utils import (
    escape_markdown_v2,
    validate_full_name,
    validate_department,
    TimesheetMessages,
    AdminMessages,
    PREDEFINED_SECTORS,
)
from ..states import ApplicationStates
from ..config import TimesheetConfig

logger = logging.getLogger(__name__)


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает нажатие кнопки 'Подать заявку на доступ'."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    logger.info(f"User {user.id} начал подачу заявки на доступ.")

    user_db_data = get_user(user.id)
    
    if user_db_data:
        is_authorized = user_db_data['is_authorized']
        application_full_name_in_db = user_db_data['application_full_name']
        
        if is_authorized == 1:
            logger.info(f"User {user.id}: Уже авторизован.")
            await query.edit_message_text(text="Вы уже авторизованы и можете пользоваться ботом.")
            return ConversationHandler.END

        if is_authorized == 0 and application_full_name_in_db:
            logger.info(f"User {user.id}: Заявка уже на рассмотрении.")
            await query.edit_message_text(text="Ваша заявка уже находится на рассмотрении.")
            return ConversationHandler.END
    
    logger.info(f"User {user.id}: Запрос ФИО.")
    
    await query.edit_message_text(
        text=escape_markdown_v2(TimesheetMessages.APPLICATION_PROMPT_NAME),
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return ApplicationStates.ASK_FULL_NAME


async def receive_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет ФИО и предлагает выбрать сектор."""
    user_id = update.effective_user.id
    full_name = update.message.text.strip()

    # Валидация
    is_valid, error_msg = validate_full_name(full_name)
    if not is_valid:
        await update.message.reply_text(error_msg)
        return ApplicationStates.ASK_FULL_NAME
    
    context.user_data['application_full_name'] = full_name
    logger.info(f"User {user_id} ввел ФИО: {full_name}")

    # Формируем клавиатуру с секторами
    keyboard = []
    for sector_display_name in PREDEFINED_SECTORS:
        parts = sector_display_name.split()
        sector_key = parts[-1].upper() if len(parts) > 1 else sector_display_name.upper()
        keyboard.append([
            InlineKeyboardButton(
                sector_display_name,
                callback_data=f"reg_select_dept_{sector_key}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("❌ Отменить заявку", callback_data="reg_cancel_direct")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = TimesheetMessages.APPLICATION_PROMPT_SECTOR.format(name=full_name)
    await update.message.reply_text(message_text, reply_markup=reply_markup)
    
    return ApplicationStates.ASK_DEPARTMENT


async def process_department_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор сектора и завершает подачу заявки."""
    query = update.callback_query
    await query.answer()
    selected_callback_data = query.data
    user = query.from_user

    logger.info(f"User {user.id} выбрал callback: {selected_callback_data}")

    if selected_callback_data == "reg_cancel_direct":
        logger.info(f"User {user.id} отменил подачу заявки.")
        await query.edit_message_text("Подача заявки отменена.")
        context.user_data.clear()
        return ConversationHandler.END

    # Извлекаем ключ сектора
    try:
        department_key = selected_callback_data.replace("reg_select_dept_", "")
    except AttributeError:
        logger.error(f"User {user.id}: Ошибка извлечения department_key из {selected_callback_data}")
        await query.edit_message_text("Произошла ошибка при выборе сектора.")
        context.user_data.clear()
        return ConversationHandler.END
        
    full_name = context.user_data.get('application_full_name')
    if not full_name:
        logger.error(f"User {user.id}: ФИО не найдено в user_data.")
        await query.edit_message_text("Произошла ошибка: не удалось найти ваше ФИО.")
        context.user_data.clear()
        return ConversationHandler.END

    context.user_data['application_department'] = department_key
    username = user.username if user.username else "N/A"
    
    logger.info(f"User {user.id}: Подготовка к сохранению заявки. ФИО: '{full_name}', Департамент: '{department_key}'")

    try:
        success, message_from_db = submit_application(
            telegram_id=user.id,
            full_name=full_name,
            department=department_key
        )

        if success:
            logger.info(f"Заявка успешно подана для ID {user.id}.")
            
            # Находим полное отображаемое имя сектора
            selected_sector_display_name = department_key
            for predefined_sector_full_name in PREDEFINED_SECTORS:
                parts = predefined_sector_full_name.split()
                abbr = parts[-1].upper() if len(parts) > 1 else predefined_sector_full_name.upper()
                if abbr == department_key.upper():
                    selected_sector_display_name = predefined_sector_full_name
                    break
            
            await query.edit_message_text(text=message_from_db)
            
            # Уведомление администраторам
            safe_first_name = escape_markdown_v2(user.first_name or '')
            safe_last_name = escape_markdown_v2(user.last_name or '')
            safe_username = escape_markdown_v2(f"@{username}" if username != 'N/A' else f"ID {user.id}")
            safe_full_name = escape_markdown_v2(full_name)
            safe_department = escape_markdown_v2(selected_sector_display_name)
            
            admin_message = AdminMessages.NEW_APPLICATION.format(
                first_name=safe_first_name,
                last_name=safe_last_name,
                username=safe_username,
                user_id=user.id,
                full_name=safe_full_name,
                department=safe_department
            )
            
            if TimesheetConfig.ADMIN_TELEGRAM_IDS:
                for admin_id in TimesheetConfig.ADMIN_TELEGRAM_IDS:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=admin_message,
                            parse_mode=ParseMode.MARKDOWN_V2
                        )
                    except Exception as e_admin:
                        logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e_admin}")
        else:
            logger.warning(f"Не удалось подать заявку для {user.id}. Сообщение: {message_from_db}")
            await query.edit_message_text(text=message_from_db)
            
    except Exception as e:
        logger.error(f"Ошибка в process_department_selection для {user.id}: {e}", exc_info=True)
        await query.edit_message_text(
            text="Произошла ошибка при обработке заявки. Попробуйте позже."
        )
    finally:
        context.user_data.clear()
        
    return ConversationHandler.END


async def cancel_application_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет диалог подачи заявки."""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} отменил диалог подачи заявки.")
    
    await update.message.reply_text(
        escape_markdown_v2("Подача заявки отменена. Вы можете начать заново."),
        parse_mode=ParseMode.MARKDOWN_V2
    )
    context.user_data.clear()
    return ConversationHandler.END


# ConversationHandler для подачи заявки
application_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(button_callback_handler, pattern='^apply_for_access$')
    ],
    states={
        ApplicationStates.ASK_FULL_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_full_name)
        ],
        ApplicationStates.ASK_DEPARTMENT: [
            CallbackQueryHandler(process_department_selection, pattern='^reg_select_dept_'),
            CallbackQueryHandler(process_department_selection, pattern='^reg_cancel_direct$')
        ],
    },
    fallbacks=[],
    name="application_flow",
    per_user=True,
    per_chat=True,
    allow_reentry=True
)