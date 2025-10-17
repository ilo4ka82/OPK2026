"""
Обработчик админской обработки ручных заявок на отметку прихода.
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
    get_pending_manual_checkin_requests,
    get_manual_checkin_request_by_id,
    approve_manual_checkin_request,
    approve_all_pending_manual_checkins,
    reject_manual_checkin_request,
)
from ...utils import (
    admin_required,
    validate_datetime_format,
    AdminMessages,
    TimesheetMessages,
    escape_markdown_v2,
)
from ...states import AdminManualCheckinStates

logger = logging.getLogger(__name__)
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


@admin_required
async def admin_manual_checkins_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает диалог обработки ручных заявок.
    Команда: /admin_manual_checkins
    """
    admin_user_id = update.effective_user.id
    logger.info(f"Админ {admin_user_id} запросил список ручных заявок на отметку.")

    pending_requests = get_pending_manual_checkin_requests()

    if not pending_requests:
        await update.message.reply_text("Нет ожидающих заявок на ручную отметку прихода.")
        return ConversationHandler.END

    # Формируем сообщение со списком
    message_lines = ["<b>📋 Заявки на ручную отметку прихода:</b>\n"]

    keyboard = []

    for req in pending_requests:
        request_id = req['request_id']
        user_id = req['user_id']
        full_name = req.get('application_full_name', 'Без имени')
        username = req.get('username', 'N/A')
        requested_time = req['requested_checkin_time']

        display_username = f"@{username}" if username != 'N/A' else f"ID {user_id}"

        message_lines.append(
            f"🆔 <b>Заявка #{request_id}</b>\n"
            f"   👤 {full_name} ({display_username})\n"
            f"   ⏰ Время: {requested_time}\n"
        )

        # Кнопки для каждой заявки
        keyboard.append([
            InlineKeyboardButton(
                f"✅ Одобрить #{request_id}",
                callback_data=f"manual_approve:{request_id}"
            ),
            InlineKeyboardButton(
                f"✏️ Изменить #{request_id}",
                callback_data=f"manual_edit:{request_id}"
            ),
            InlineKeyboardButton(
                f"❌ Отклонить #{request_id}",
                callback_data=f"manual_reject:{request_id}"
            )
        ])

    # Кнопка массового одобрения
    keyboard.append([
        InlineKeyboardButton(
            "✅ Одобрить ВСЕ заявки",
            callback_data="manual_approve_all"
        )
    ])

    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="manual_cancel")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = "\n".join(message_lines)

    await update.message.reply_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

    return AdminManualCheckinStates.LIST_REQUESTS


async def process_manual_request_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает действия админа: одобрить, изменить, отклонить.
    """
    query = update.callback_query
    await query.answer()

    callback_data_str = query.data
    admin_user_id = query.from_user.id

    try:
        # === ОТМЕНА ===
        if callback_data_str == "manual_cancel":
            await query.edit_message_text("Обработка ручных заявок отменена.")
            context.user_data.clear()
            return ConversationHandler.END

        # === МАССОВОЕ ОДОБРЕНИЕ ===
        elif callback_data_str == "manual_approve_all":
            logger.info(f"Админ {admin_user_id} начал массовое одобрение ручных заявок.")

            approved_list, failed_count = approve_all_pending_manual_checkins(admin_user_id)

            # Отправляем уведомления пользователям
            sent_count = 0
            for approved_data in approved_list:
                try:
                    target_user_id = approved_data['user_id']
                    checkin_time_str = approved_data['checkin_time_str']

                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=TimesheetMessages.MANUAL_REQUEST_APPROVED.format(time=checkin_time_str)
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")

            summary_message = AdminMessages.MASS_APPROVAL_COMPLETE.format(
                approved=len(approved_list),
                sent=sent_count,
                failed=failed_count
            )

            await query.edit_message_text(summary_message)
            context.user_data.clear()
            return ConversationHandler.END

        # === ОДОБРЕНИЕ ОДНОЙ ЗАЯВКИ ===
        elif callback_data_str.startswith("manual_approve:"):
            request_id = int(callback_data_str.split(":")[1])
            logger.info(f"Админ {admin_user_id} одобряет заявку #{request_id}")

            request_data = get_manual_checkin_request_by_id(request_id)
            if not request_data:
                await query.edit_message_text(f"Заявка #{request_id} не найдена.")
                return ConversationHandler.END

            user_id = request_data['user_id']
            requested_time_str = request_data['requested_checkin_time']
            user_sector_key = request_data.get('application_department', 'unknown')

            # Парсим время
            try:
                final_dt = datetime.strptime(requested_time_str, '%Y-%m-%d %H:%M:%S')
                final_dt_moscow = MOSCOW_TZ.localize(final_dt)
            except ValueError:
                await query.edit_message_text(f"Ошибка парсинга времени для заявки #{request_id}")
                return ConversationHandler.END

            success = approve_manual_checkin_request(
                request_id=request_id,
                admin_id=admin_user_id,
                final_checkin_time=final_dt_moscow,
                user_id=user_id,
                user_sector_key=user_sector_key
            )

            if success:
                # Уведомляем пользователя
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=TimesheetMessages.MANUAL_REQUEST_APPROVED.format(time=requested_time_str)
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

                user_name = request_data.get('application_full_name', f"ID {user_id}")
                success_msg = AdminMessages.MANUAL_REQUEST_APPROVED.format(
                    name=user_name,
                    action="одобрена",
                    time=requested_time_str
                )
                await query.edit_message_text(success_msg)
            else:
                await query.edit_message_text(f"Не удалось одобрить заявку #{request_id}")

            context.user_data.clear()
            return ConversationHandler.END

        # === ОТКЛОНЕНИЕ ЗАЯВКИ ===
        elif callback_data_str.startswith("manual_reject:"):
            request_id = int(callback_data_str.split(":")[1])
            logger.info(f"Админ {admin_user_id} отклоняет заявку #{request_id}")

            request_data = get_manual_checkin_request_by_id(request_id)
            if not request_data:
                await query.edit_message_text(f"Заявка #{request_id} не найдена.")
                return ConversationHandler.END

            user_id = request_data['user_id']

            success = reject_manual_checkin_request(request_id, admin_user_id)

            if success:
                # Уведомляем пользователя
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=TimesheetMessages.MANUAL_REQUEST_REJECTED
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

                user_name = request_data.get('application_full_name', f"ID {user_id}")
                await query.edit_message_text(
                    AdminMessages.MANUAL_REQUEST_REJECTED.format(name=user_name)
                )
            else:
                await query.edit_message_text(f"Не удалось отклонить заявку #{request_id}")

            context.user_data.clear()
            return ConversationHandler.END

        # === ИЗМЕНЕНИЕ ВРЕМЕНИ ===
        elif callback_data_str.startswith("manual_edit:"):
            request_id = int(callback_data_str.split(":")[1])
            logger.info(f"Админ {admin_user_id} хочет изменить время для заявки #{request_id}")

            request_data = get_manual_checkin_request_by_id(request_id)
            if not request_data:
                await query.edit_message_text(f"Заявка #{request_id} не найдена.")
                return ConversationHandler.END

            context.user_data['manual_request_id_to_edit'] = request_id
            context.user_data['manual_request_user_id'] = request_data['user_id']
            context.user_data['manual_request_sector'] = request_data.get('application_department', 'unknown')

            await query.edit_message_text(
                f"Введите новое время прихода для заявки #{request_id}\n"
                f"Формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
                f"Например: 15.01.2025 09:00"
            )

            return AdminManualCheckinStates.ENTER_NEW_TIME

        else:
            logger.warning(f"Неизвестный callback: {callback_data_str}")
            await query.answer("Неизвестное действие")
            return AdminManualCheckinStates.LIST_REQUESTS

    except Exception as e:
        logger.error(f"Ошибка в process_manual_request_action: {e}", exc_info=True)
        await query.edit_message_text("Произошла ошибка при обработке заявки.")
        context.user_data.clear()
        return ConversationHandler.END


async def receive_new_time_for_manual_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Получает новое время от админа для ручной заявки.
    """
    admin_user_id = update.effective_user.id
    new_time_input = update.message.text.strip()

    request_id = context.user_data.get('manual_request_id_to_edit')
    user_id = context.user_data.get('manual_request_user_id')
    user_sector = context.user_data.get('manual_request_sector')

    if not request_id or not user_id:
        await update.message.reply_text("Произошла ошибка: данные заявки не найдены.")
        context.user_data.clear()
        return ConversationHandler.END

    # Валидация формата
    is_valid, dt_obj, error_msg = validate_datetime_format(new_time_input, '%d.%m.%Y %H:%M')

    if not is_valid:
        await update.message.reply_text(
            f"Неверный формат времени.\n{error_msg}\n\n"
            f"Попробуйте еще раз или отправьте /cancel для отмены."
        )
        return AdminManualCheckinStates.ENTER_NEW_TIME

    try:
        final_dt_moscow = MOSCOW_TZ.localize(dt_obj)

        success = approve_manual_checkin_request(
            request_id=request_id,
            admin_id=admin_user_id,
            final_checkin_time=final_dt_moscow,
            user_id=user_id,
            user_sector_key=user_sector
        )

        if success:
            time_str = final_dt_moscow.strftime('%d.%m.%Y %H:%M')

            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=TimesheetMessages.MANUAL_REQUEST_APPROVED.format(time=time_str)
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

            await update.message.reply_text(
                f"✅ Заявка #{request_id} одобрена с измененным временем: {time_str}"
            )
        else:
            await update.message.reply_text(f"Не удалось обработать заявку #{request_id}")

        context.user_data.clear()
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка в receive_new_time_for_manual_request: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при обработке времени.")
        context.user_data.clear()
        return ConversationHandler.END


async def cancel_manual_checkins_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет диалог обработки ручных заявок."""
    await update.message.reply_text("Обработка ручных заявок отменена.")
    context.user_data.clear()
    return ConversationHandler.END


# ConversationHandler для админской обработки ручных заявок
admin_manual_checkins_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("admin_manual_checkins", admin_manual_checkins_start)
    ],
    states={
        AdminManualCheckinStates.LIST_REQUESTS: [
            CallbackQueryHandler(process_manual_request_action)
        ],
        AdminManualCheckinStates.ENTER_NEW_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_time_for_manual_request)
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_manual_checkins_dialog)
    ],
    name="admin_manual_checkins_flow",
    per_user=True,
    per_chat=True,
    allow_reentry=True
)
