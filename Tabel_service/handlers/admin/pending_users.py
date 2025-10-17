"""
Обработчик просмотра и обработки ожидающих заявок пользователей.
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ...database import (
    list_pending_users,
    authorize_user,
    reject_application,
    get_user,
)
from ...utils import (
    admin_required,
    escape_markdown_v2,
    AdminMessages,
    TimesheetMessages,
    ITEMS_PER_PAGE,
)
from ...keyboards import get_pagination_keyboard

logger = logging.getLogger(__name__)


@admin_required
async def admin_pending_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда /admin_pending_users - показывает список ожидающих пользователей с пагинацией.
    """
    admin_user_id = update.effective_user.id
    logger.info(f"Админ {admin_user_id} запросил список ожидающих пользователей.")

    pending_users_list = list_pending_users()

    if not pending_users_list:
        await update.message.reply_text("Нет пользователей, ожидающих авторизации.")
        return

    # Первая страница
    await _send_pending_users_page(
        update=update,
        context=context,
        pending_users=pending_users_list,
        page=1,
        message_to_edit=None
    )


async def admin_action_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает callback-и для авторизации, отклонения и пагинации.
    
    Форматы callback_data:
    - authorize_user:USER_ID
    - reject_user:USER_ID
    - paginate_list:PAGE:FOCUSED_USER_ID
    """
    query = update.callback_query
    await query.answer()

    callback_data_str = query.data
    admin_user_id = query.from_user.id

    try:
        # === АВТОРИЗАЦИЯ ПОЛЬЗОВАТЕЛЯ ===
        if callback_data_str.startswith("authorize_user:"):
            user_id_to_authorize = int(callback_data_str.split(":")[1])
            logger.info(f"Админ {admin_user_id} авторизует пользователя {user_id_to_authorize}")

            success, message_from_db = authorize_user(user_id_to_authorize, admin_user_id)

            if success:
                # Отправляем уведомление пользователю
                try:
                    await context.bot.send_message(
                        chat_id=user_id_to_authorize,
                        text=TimesheetMessages.APPLICATION_APPROVED_NOTIFICATION
                    )
                    logger.info(f"Уведомление об одобрении отправлено пользователю {user_id_to_authorize}")
                except Exception as e:
                    logger.error(
                        f"Не удалось отправить уведомление пользователю {user_id_to_authorize}: {e}"
                    )

                # Обновляем список
                pending_users_list = list_pending_users()
                if pending_users_list:
                    await _send_pending_users_page(
                        update=update,
                        context=context,
                        pending_users=pending_users_list,
                        page=1,
                        message_to_edit=query.message
                    )
                else:
                    await query.edit_message_text(
                        "✅ Пользователь авторизован.\n\nБольше нет пользователей, ожидающих авторизации."
                    )
            else:
                await query.edit_message_text(
                    escape_markdown_v2(message_from_db),
                    parse_mode=ParseMode.MARKDOWN_V2
                )

        # === ОТКЛОНЕНИЕ ЗАЯВКИ ===
        elif callback_data_str.startswith("reject_user:"):
            user_id_to_reject = int(callback_data_str.split(":")[1])
            logger.info(f"Админ {admin_user_id} отклоняет заявку пользователя {user_id_to_reject}")

            success, message_from_db = reject_application(user_id_to_reject, admin_user_id)

            if success:
                # Отправляем уведомление пользователю
                try:
                    await context.bot.send_message(
                        chat_id=user_id_to_reject,
                        text=TimesheetMessages.APPLICATION_REJECTED_NOTIFICATION
                    )
                    logger.info(f"Уведомление об отклонении отправлено пользователю {user_id_to_reject}")
                except Exception as e:
                    logger.error(
                        f"Не удалось отправить уведомление пользователю {user_id_to_reject}: {e}"
                    )

                # Обновляем список
                pending_users_list = list_pending_users()
                if pending_users_list:
                    await _send_pending_users_page(
                        update=update,
                        context=context,
                        pending_users=pending_users_list,
                        page=1,
                        message_to_edit=query.message
                    )
                else:
                    await query.edit_message_text(
                        "🚫 Заявка отклонена.\n\nБольше нет пользователей, ожидающих авторизации."
                    )
            else:
                await query.edit_message_text(
                    escape_markdown_v2(message_from_db),
                    parse_mode=ParseMode.MARKDOWN_V2
                )

        # === ПАГИНАЦИЯ ===
        elif callback_data_str.startswith("paginate_list:"):
            parts = callback_data_str.split(":")
            new_page = int(parts[1])
            
            pending_users_list = list_pending_users()
            
            if pending_users_list:
                await _send_pending_users_page(
                    update=update,
                    context=context,
                    pending_users=pending_users_list,
                    page=new_page,
                    message_to_edit=query.message
                )
            else:
                await query.edit_message_text("Больше нет пользователей, ожидающих авторизации.")

        else:
            logger.warning(f"Неизвестный callback_data: {callback_data_str}")
            await query.answer("Неизвестное действие.")

    except Exception as e:
        logger.error(f"Ошибка в admin_action_callback_handler: {e}", exc_info=True)
        await query.edit_message_text("Произошла ошибка при обработке действия.")


async def _send_pending_users_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    pending_users: list,
    page: int,
    message_to_edit=None
) -> None:
    """
    Вспомогательная функция для отправки страницы со списком ожидающих пользователей.
    
    Args:
        update: Update объект
        context: Context объект
        pending_users: Список пользователей
        page: Номер страницы (начиная с 1)
        message_to_edit: Сообщение для редактирования (None для нового)
    """
    total_users = len(pending_users)
    total_pages = (total_users + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_index = (page - 1) * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    users_on_page = pending_users[start_index:end_index]

    message_lines = [f"📋 <b>Ожидающие авторизации (стр. {page}/{total_pages}):</b>\n"]

    for user_data in users_on_page:
        user_id = user_data.get('telegram_id', 'N/A')
        username = user_data.get('username', 'N/A')
        first_name = user_data.get('first_name', '')
        last_name = user_data.get('last_name', '')
        full_name_from_app = user_data.get('application_full_name', 'Не указано')
        department = user_data.get('application_department', 'Не указан')

        display_username = f"@{username}" if username and username != 'N/A' else f"ID: {user_id}"
        display_name = f"{first_name} {last_name}".strip() or "Без имени"

        message_lines.append(
            f"👤 <b>{display_name}</b> ({display_username})\n"
            f"   📝 ФИО: {full_name_from_app}\n"
            f"   🏢 Сектор: {department}\n"
        )

    message_text = "\n".join(message_lines)

    # Формируем клавиатуру
    keyboard = []

    # Кнопки авторизации/отклонения для каждого пользователя
    for user_data in users_on_page:
        user_id = user_data['telegram_id']
        display_name = user_data.get('application_full_name', f"ID {user_id}")
        
        if len(display_name) > 20:
            display_name = display_name[:17] + "..."

        keyboard.append([
            InlineKeyboardButton(
                f"✅ {display_name}",
                callback_data=f"authorize_user:{user_id}"
            ),
            InlineKeyboardButton(
                f"❌ {display_name}",
                callback_data=f"reject_user:{user_id}"
            )
        ])

    # Пагинация
    if total_pages > 1:
        pagination_keyboard = get_pagination_keyboard(page, total_users, ITEMS_PER_PAGE)
        keyboard.extend(pagination_keyboard.inline_keyboard)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if message_to_edit:
        await message_to_edit.edit_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )