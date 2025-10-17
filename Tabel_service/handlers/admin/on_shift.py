"""
Обработчик просмотра сотрудников на смене.
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ...database import get_unique_user_departments, get_active_users_by_department
from ...utils import admin_required, AdminMessages
from ...keyboards import get_department_selection_keyboard

logger = logging.getLogger(__name__)


@admin_required
async def on_shift_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда /on_shift - показывает сотрудников на смене.
    """
    logger.info(f"Админ {update.effective_user.id} вызвал команду /on_shift")
    
    departments = get_unique_user_departments()
    
    if not departments:
        await update.message.reply_text("В базе данных не найдено пользователей с указанными департаментами.")
        return

    reply_markup = get_department_selection_keyboard(departments)
    await update.message.reply_text(AdminMessages.ON_SHIFT_SELECT_DEPT, reply_markup=reply_markup)


async def on_shift_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает нажатие на кнопку выбора департамента.
    Форматирует вывод в виде таблицы с выравниванием.
    """
    query = update.callback_query
    await query.answer()

    try:
        command, _, department_choice = query.data.partition(':')

        if command == "on_shift_cancel":
            await query.edit_message_text("Действие отменено.")
            return
            
        logger.info(f"Админ {query.from_user.id} запросил список на смене для департамента: {department_choice}")

        active_users = get_active_users_by_department(department_choice)

        display_header = "Все" if department_choice == "ALL" else department_choice
        message_text = f"<b>👥 Сотрудники на смене (Департамент: {display_header})</b>\n"

        if not active_users:
            message_text += "\nНа смене никого нет."
            await query.edit_message_text(text=message_text, parse_mode=ParseMode.HTML)
            return

        formatted_lines = {}
        
        for user in active_users:
            display_name = user['application_full_name'] or user['username'] or 'Без имени'

            try:
                from datetime import datetime
                checkin_dt = datetime.strptime(user['check_in_time'], '%Y-%m-%d %H:%M:%S')
                checkin_time_str = checkin_dt.strftime('%H:%M')
            except (ValueError, TypeError):
                checkin_time_str = "??:??"
            
            department = user['application_department'] or "Без департамента"
            
            if department not in formatted_lines:
                formatted_lines[department] = []
            formatted_lines[department].append({'name': display_name, 'time': checkin_time_str})

        max_name_length = 0
        for dept_lines in formatted_lines.values():
            for line in dept_lines:
                if len(line['name']) > max_name_length:
                    max_name_length = len(line['name'])
        
        for department, employees in sorted(formatted_lines.items()):
            message_text += f"\n<b>{department}:</b>\n"
            
            table_rows = []
            for emp in employees:
                aligned_name = emp['name'].ljust(max_name_length)
                table_rows.append(f"<code>{aligned_name}  |  {emp['time']}</code>")
            
            message_text += "\n".join(table_rows)
            
        await query.edit_message_text(text=message_text, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Критическая ошибка в on_shift_button_press: {e}", exc_info=True)
        await query.edit_message_text("Произошла внутренняя ошибка при формировании списка. Пожалуйста, проверьте логи.")