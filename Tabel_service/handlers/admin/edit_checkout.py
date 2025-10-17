"""
Обработчик редактирования времени ухода администратором.
"""
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode
import pytz

from ...database import (
    find_users_by_name,
    get_completed_sessions_for_user,
    update_session_checkout_time,
)
from ...utils import (
    admin_required,
    validate_datetime_format,
    parse_datetime_from_db,
    datetime_to_db_string,
    AdminMessages,
    SESSIONS_PER_PAGE,
)
from ...states import EditCheckoutStates

logger = logging.getLogger(__name__)
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


@admin_required
async def edit_checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает диалог редактирования времени ухода.
    Команда: /edit_checkout
    """
    admin_user_id = update.effective_user.id
    logger.info(f"Админ {admin_user_id} начал процесс редактирования времени ухода.")

    await update.message.reply_text(AdminMessages.EDIT_PROMPT_NAME)
    
    return EditCheckoutStates.AWAIT_NAME


async def receive_user_name_for_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает имя пользователя и показывает список найденных."""
    name_input = update.message.text.strip()
    
    if len(name_input) < 3:
        await update.message.reply_text(
            "Пожалуйста, введите не менее 3 символов для поиска.\n"
            "Или /cancel для отмены."
        )
        return EditCheckoutStates.AWAIT_NAME
    
    found_users = find_users_by_name(name_input)
    
    if not found_users:
        await update.message.reply_text(
            f"Пользователи с именем '{name_input}' не найдены.\n"
            "Попробуйте ввести другое имя или /cancel для отмены."
        )
        return EditCheckoutStates.AWAIT_NAME
    
    if len(found_users) == 1:
        # Сразу выбираем единственного пользователя
        user_id = found_users[0]['telegram_id']
        user_name = found_users[0]['application_full_name']
        
        context.user_data['edit_target_user_id'] = user_id
        context.user_data['edit_target_user_name'] = user_name
        
        return await _show_period_selection(update, context, user_name)
    
    # Показываем список для выбора
    keyboard = []
    for user in found_users:
        user_id = user['telegram_id']
        user_name = user['application_full_name']
        keyboard.append([
            InlineKeyboardButton(
                user_name,
                callback_data=f"edit_select_user:{user_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="edit_cancel")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Найдено {len(found_users)} пользователей. Выберите нужного:",
        reply_markup=reply_markup
    )
    
    return EditCheckoutStates.SELECT_USER


async def process_user_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор пользователя из списка."""
    query = update.callback_query
    await query.answer()

    if query.data == "edit_cancel":
        await query.edit_message_text("Редактирование отменено.")
        context.user_data.clear()
        return ConversationHandler.END
    
    user_id = int(query.data.split(":")[1])
    
    # Получаем имя пользователя
    found_users = find_users_by_name("")  # Получаем всех, чтобы найти по ID
    user_name = None
    for user in found_users:
        if user['telegram_id'] == user_id:
            user_name = user['application_full_name']
            break
    
    if not user_name:
        await query.edit_message_text("Ошибка: пользователь не найден.")
        context.user_data.clear()
        return ConversationHandler.END
    
    context.user_data['edit_target_user_id'] = user_id
    context.user_data['edit_target_user_name'] = user_name
    
    return await _show_period_selection_query(query, context, user_name)


async def _show_period_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, user_name: str) -> int:
    """Показывает выбор периода для просмотра сессий."""
    keyboard = [
        [InlineKeyboardButton("Последние 5 сессий", callback_data="edit_period_last5")],
        [InlineKeyboardButton("За последнюю неделю", callback_data="edit_period_week")],
        [InlineKeyboardButton("За последний месяц", callback_data="edit_period_month")],
        [InlineKeyboardButton("❌ Отмена", callback_data="edit_cancel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = AdminMessages.EDIT_USER_SELECTED.format(name=user_name)
    
    await update.message.reply_text(text, reply_markup=reply_markup)
    
    return EditCheckoutStates.SELECT_PERIOD


async def _show_period_selection_query(query, context: ContextTypes.DEFAULT_TYPE, user_name: str) -> int:
    """Показывает выбор периода (через callback query)."""
    keyboard = [
        [InlineKeyboardButton("Последние 5 сессий", callback_data="edit_period_last5")],
        [InlineKeyboardButton("За последнюю неделю", callback_data="edit_period_week")],
        [InlineKeyboardButton("За последний месяц", callback_data="edit_period_month")],
        [InlineKeyboardButton("❌ Отмена", callback_data="edit_cancel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = AdminMessages.EDIT_USER_SELECTED.format(name=user_name)
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    
    return EditCheckoutStates.SELECT_PERIOD


async def process_period_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор периода и показывает сессии."""
    query = update.callback_query
    await query.answer()

    if query.data == "edit_cancel":
        await query.edit_message_text("Редактирование отменено.")
        context.user_data.clear()
        return ConversationHandler.END
    
    period = query.data.replace("edit_period_", "")
    user_id = context.user_data.get('edit_target_user_id')
    user_name = context.user_data.get('edit_target_user_name')
    
    if not user_id:
        await query.edit_message_text("Ошибка: пользователь не выбран.")
        context.user_data.clear()
        return ConversationHandler.END
    
    sessions = get_completed_sessions_for_user(user_id, period)
    
    if not sessions:
        await query.edit_message_text(
            AdminMessages.ERROR_NO_SESSIONS.format(name=user_name)
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # Показываем список сессий
    keyboard = []
    for session in sessions[:SESSIONS_PER_PAGE]:  # Ограничиваем количество
        session_id = session['session_id']
        checkin = session['check_in_time']
        checkout = session.get('check_out_time', 'Активна')
        
        try:
            checkin_dt = parse_datetime_from_db(checkin)
            date_str = checkin_dt.strftime('%d.%m.%Y')
            time_str = checkin_dt.strftime('%H:%M')
        except:
            date_str = checkin
            time_str = ""
        
        button_text = f"{date_str} {time_str}"
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"edit_session:{session_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="edit_cancel")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Выберите сессию для редактирования:",
        reply_markup=reply_markup
    )
    
    return EditCheckoutStates.SELECT_SESSION


async def process_session_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор сессии."""
    query = update.callback_query
    await query.answer()

    if query.data == "edit_cancel":
        await query.edit_message_text("Редактирование отменено.")
        context.user_data.clear()
        return ConversationHandler.END
    
    session_id = int(query.data.split(":")[1])
    context.user_data['edit_session_id'] = session_id
    
    # Получаем информацию о сессии
    user_id = context.user_data.get('edit_target_user_id')
    sessions = get_completed_sessions_for_user(user_id, 'last5')
    
    selected_session = None
    for session in sessions:
        if session['session_id'] == session_id:
            selected_session = session
            break
    
    if not selected_session:
        await query.edit_message_text("Ошибка: сессия не найдена.")
        context.user_data.clear()
        return ConversationHandler.END
    
    current_checkout = selected_session.get('check_out_time', 'Не установлено')
    checkin_time = selected_session['check_in_time']
    
    try:
        checkin_dt = parse_datetime_from_db(checkin_time)
        date_str = checkin_dt.strftime('%d.%m.%Y')
    except:
        date_str = checkin_time
    
    text = AdminMessages.EDIT_SESSION_SELECTED.format(
        date=date_str,
        current_time=current_checkout
    )
    
    await query.edit_message_text(text)
    
    return EditCheckoutStates.AWAIT_NEW_TIME


async def receive_new_checkout_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает новое время ухода от админа."""
    time_input = update.message.text.strip()
    
    is_valid, dt_obj, error_msg = validate_datetime_format(time_input, '%d.%m.%Y %H:%M')
    
    if not is_valid:
        await update.message.reply_text(
            f"Неверный формат времени.\n{error_msg}\n\n"
            "Попробуйте еще раз или /cancel для отмены."
        )
        return EditCheckoutStates.AWAIT_NEW_TIME
    
    # Локализуем в московское время
    new_checkout_dt = MOSCOW_TZ.localize(dt_obj)
    context.user_data['edit_new_checkout_time'] = new_checkout_dt
    
    user_name = context.user_data.get('edit_target_user_name', 'пользователя')
    time_str = new_checkout_dt.strftime('%d.%m.%Y %H:%M')
    
    confirmation_text = AdminMessages.EDIT_CONFIRM.format(
        name=user_name,
        time=time_str
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, изменить", callback_data="edit_confirm_yes")],
        [InlineKeyboardButton("❌ Отменить", callback_data="edit_cancel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
    
    return EditCheckoutStates.CONFIRM


async def process_edit_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает подтверждение изменения."""
    query = update.callback_query
    await query.answer()

    if query.data == "edit_cancel":
        await query.edit_message_text("Редактирование отменено.")
        context.user_data.clear()
        return ConversationHandler.END
    
    if query.data == "edit_confirm_yes":
        session_id = context.user_data.get('edit_session_id')
        new_checkout_dt = context.user_data.get('edit_new_checkout_time')
        
        if not session_id or not new_checkout_dt:
            await query.edit_message_text("Ошибка: данные не найдены.")
            context.user_data.clear()
            return ConversationHandler.END
        
        # Конвертируем в строку для БД
        new_checkout_str = datetime_to_db_string(new_checkout_dt)
        
        success = update_session_checkout_time(session_id, new_checkout_str)
        
        if success:
            await query.edit_message_text(AdminMessages.EDIT_SUCCESS)
        else:
            await query.edit_message_text("Не удалось изменить время ухода.")
        
        context.user_data.clear()
        return ConversationHandler.END
    
    return EditCheckoutStates.CONFIRM


async def cancel_edit_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет диалог редактирования."""
    await update.message.reply_text("Редактирование отменено.")
    context.user_data.clear()
    return ConversationHandler.END


# ConversationHandler для редактирования времени ухода
edit_checkout_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("edit_checkout", edit_checkout_start)
    ],
    states={
        EditCheckoutStates.AWAIT_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_name_for_edit)
        ],
        EditCheckoutStates.SELECT_USER: [
            CallbackQueryHandler(process_user_selection)
        ],
        EditCheckoutStates.SELECT_PERIOD: [
            CallbackQueryHandler(process_period_selection)
        ],
        EditCheckoutStates.SELECT_SESSION: [
            CallbackQueryHandler(process_session_selection)
        ],
        EditCheckoutStates.AWAIT_NEW_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_checkout_time)
        ],
        EditCheckoutStates.CONFIRM: [
            CallbackQueryHandler(process_edit_confirmation)
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_edit_dialog)
    ],
    name="edit_checkout_flow",
    per_user=True,
    per_chat=True,
    allow_reentry=True
)
