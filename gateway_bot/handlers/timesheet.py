"""
Обработчики табеля (используют database из Tabel_service на aiogram 2.x).
ПОЛНАЯ ВЕРСИЯ с проверками и ручными заявками.
"""
import sys
import os
from datetime import datetime, timezone, timedelta
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# Добавляем родительскую папку в sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Импортируем из Tabel_service
from Tabel_service.database import (
    get_user,
    add_or_update_user,
    is_user_authorized,
    record_check_in,
    record_check_out,
    add_manual_checkin_request,
    get_pending_manual_checkin_requests,
    get_manual_checkin_request_by_id,
    approve_manual_checkin_request,
    reject_manual_checkin_request,
    approve_all_pending_manual_checkins,
)
import pytz

from Tabel_service.utils import (
    is_within_office_zone,
    validate_location_age,
    TimesheetMessages,
    MAX_LOCATION_AGE_SECONDS,
    MOSCOW_TZ,
)

from config import config
from keyboards import (
    get_timesheet_menu, 
    get_main_menu,
    get_location_keyboard,
    get_manual_checkins_keyboard,
)
from states import BotStates


# ============================================================================
# БАЗОВЫЙ ФУНКЦИОНАЛ: CHECK-IN / CHECK-OUT
# ============================================================================

async def timesheet_menu_handler(message: types.Message, state: FSMContext):
    """Обработчик меню табеля"""
    text = message.text
    user_id = message.from_user.id
    
    # Добавляем/обновляем пользователя в БД
    add_or_update_user(
        telegram_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Проверка авторизации
    if not is_user_authorized(user_id) and user_id not in config.ADMIN_USERS:
        await message.answer(
            "❌ Вы не авторизованы для использования табеля.\n"
            "Обратитесь к администратору.",
            reply_markup=get_main_menu()
        )
        await BotStates.main_menu.set()
        return
    
    if text == "▶️ Начать смену":
        # Запрашиваем геолокацию
        await message.answer(
            "📍 Для отметки прихода отправьте вашу <b>текущую</b> геолокацию.\n\n"
            "⚠️ <i>Внимание:</i>\n"
            "• Геолокация должна быть свежей (не старше 5 минут)\n"
            "• Пересылка геолокаций запрещена\n"
            "• Вы должны находиться в зоне офиса",
            parse_mode="HTML",
            reply_markup=get_location_keyboard()
        )
        await BotStates.timesheet_waiting_location.set()
    
    elif text == "⏹️ Закончить смену":
        success, message_text = record_check_out(user_id)
        await message.answer(message_text, reply_markup=get_timesheet_menu())
    
    elif text == "📊 Моя статистика":
        user_data = get_user(user_id)
        
        if user_data:
            full_name = user_data.get('application_full_name', 'Не указано')
            department = user_data.get('application_department', 'Не указан')
            
            await message.answer(
                f"📊 <b>Ваша статистика</b>\n\n"
                f"👤 ФИО: {full_name}\n"
                f"🏢 Сектор: {department}\n\n"
                f"<i>Детальная статистика в разработке...</i>",
                parse_mode="HTML",
                reply_markup=get_timesheet_menu()
            )
        else:
            await message.answer(
                "❌ Данные не найдены",
                reply_markup=get_timesheet_menu()
            )
    
    elif text == "🛠️ Ручная заявка":
        await message.answer(
            "🛠️ <b>Ручная заявка на отметку прихода</b>\n\n"
            "Используйте эту функцию если:\n"
            "• Забыли отметиться вовремя\n"
            "• Геолокация не сработала\n"
            "• Были технические проблемы\n\n"
            "Укажите фактическое время вашего прихода в формате:\n"
            "<code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n\n"
            "Например: <code>27.10.2025 09:15</code>\n\n"
            "Для отмены отправьте /cancel",
            parse_mode="HTML"
        )
        await BotStates.timesheet_manual_request_time.set()
    
    elif text == "◀️ Главное меню":
        await message.answer(
            "🏠 Главное меню",
            reply_markup=get_main_menu()
        )
        await BotStates.main_menu.set()
    
    else:
        await message.answer(
            "❓ Используйте кнопки меню",
            reply_markup=get_timesheet_menu()
        )


async def location_handler(message: types.Message, state: FSMContext):
    """
    УЛУЧШЕННЫЙ обработчик геолокации с проверками.
    """
    user_id = message.from_user.id
    
    # === ПРОВЕРКА №1: ПЕРЕСЫЛКА ===
    if message.forward_from or message.forward_from_chat:
        await message.answer(
            "❌ <b>Пересылка геолокации запрещена!</b>\n\n"
            "Пожалуйста, отправьте вашу <b>текущую</b> геолокацию, "
            "а не переслано старую.",
            parse_mode="HTML",
            reply_markup=get_timesheet_menu()
        )
        await BotStates.timesheet_menu.set()
        return
    
    # === ПРОВЕРКА №2: ВОЗРАСТ ГЕОЛОКАЦИИ ===
    message_date = message.date
    if not message_date.tzinfo:
        message_date = message_date.replace(tzinfo=timezone.utc)
    
    is_valid_age, age_seconds = validate_location_age(
        message_date, 
        MAX_LOCATION_AGE_SECONDS
    )
    
    if not is_valid_age:
        await message.answer(
            f"❌ <b>Геолокация слишком старая!</b>\n\n"
            f"Возраст геолокации: {age_seconds} секунд\n"
            f"Максимально допустимо: {MAX_LOCATION_AGE_SECONDS} секунд\n\n"
            f"Пожалуйста, отправьте <b>свежую</b> геолокацию.\n\n"
            f"<i>Если у вас iOS, убедитесь что отправляете "
            f"геолокацию через кнопку, а не из истории.</i>",
            parse_mode="HTML",
            reply_markup=get_timesheet_menu()
        )
        await BotStates.timesheet_menu.set()
        return
    
    # === ПРОВЕРКА №3: ГЕОЗОНА ===
    location = message.location
    latitude = location.latitude
    longitude = location.longitude
    
    if not is_within_office_zone(latitude, longitude):
        await message.answer(
            TimesheetMessages.CHECKIN_OUTSIDE_ZONE,
            reply_markup=get_timesheet_menu()
        )
        await BotStates.timesheet_menu.set()
        return
    
    # === ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ → ОТМЕТКА ПРИХОДА ===
    success, message_text = record_check_in(user_id, latitude, longitude)
    await message.answer(message_text, reply_markup=get_timesheet_menu())
    await BotStates.timesheet_menu.set()


# ============================================================================
# РУЧНЫЕ ЗАЯВКИ: ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ
# ============================================================================

async def process_manual_checkin_time(update: types.Message, state: FSMContext):
    """
    Обрабатывает введенное пользователем время для ручной отметки.
    """
    user = update.from_user
    user_input_time_str = update.text
    
    try:
        # Парсим введенное время
        naive_dt = datetime.strptime(user_input_time_str, '%d.%m.%Y %H:%M')
        
        # Делаем его московским
        moscow_dt = MOSCOW_TZ.localize(naive_dt)
        
        # Сохраняем в базу
        success = add_manual_checkin_request(
            user_id=user.id, 
            requested_checkin_time=moscow_dt
        )
        
        if success:
            await update.answer(
                f"✅ <b>Заявка принята!</b>\n\n"
                f"Запрошенное время: <code>{moscow_dt.strftime('%d.%m.%Y %H:%M')}</code>\n\n"
                f"Администратор рассмотрит вашу заявку в ближайшее время.\n"
                f"Вы получите уведомление о результате.",
                parse_mode="HTML",
                reply_markup=get_timesheet_menu()
            )
            
            # Уведомляем администраторов
            await notify_admins_new_manual_request(update.bot, user, moscow_dt)
        else:
            await update.answer(
                "❌ Произошла ошибка при сохранении заявки.\n"
                "Попробуйте позже или свяжитесь с администратором.",
                reply_markup=get_timesheet_menu()
            )
        
        await BotStates.timesheet_menu.set()
        
    except ValueError:
        await update.answer(
            "❌ <b>Неверный формат времени!</b>\n\n"
            "Пожалуйста, введите время в формате:\n"
            "<code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n\n"
            "Например: <code>27.10.2025 09:15</code>\n\n"
            "Для отмены отправьте /cancel",
            parse_mode="HTML"
        )
        return  # Остаемся в том же состоянии


async def notify_admins_new_manual_request(bot, requesting_user, requested_time: datetime):
    """Уведомляет администраторов о новой заявке."""
    
    # Получаем данные пользователя из БД
    user_profile = get_user(requesting_user.id)
    
    # Определяем отображаемое имя
    if user_profile and user_profile.get('application_full_name'):
        display_name = user_profile['application_full_name']
    else:
        display_name = requesting_user.full_name
    
    # Определяем сектор
    department_name = "Не указан"
    if user_profile and user_profile.get('application_department'):
        department_name = user_profile['application_department']
    
    username = requesting_user.username or "N/A"
    requested_time_str = requested_time.strftime('%d.%m.%Y %H:%M')
    
    message_text = (
        f"‼️ <b>Новая заявка на ручную отметку прихода!</b>\n\n"
        f"👤 <b>Сотрудник:</b> {display_name} (@{username})\n"
        f"🆔 <b>Telegram ID:</b> <code>{requesting_user.id}</code>\n"
        f"🏢 <b>Сектор:</b> {department_name}\n"
        f"⏰ <b>Запрошенное время:</b> {requested_time_str}\n\n"
        f"Для обработки заявок используйте:\n"
        f"/admin_manual_checkins"
    )
    
    if not config.ADMIN_USERS:
        return
    
    for admin_id in config.ADMIN_USERS:
        try:
            await bot.send_message(
                chat_id=admin_id, 
                text=message_text, 
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Не удалось отправить уведомление админу {admin_id}: {e}")


# ============================================================================
# РУЧНЫЕ ЗАЯВКИ: АДМИНСКАЯ ЧАСТЬ
# ============================================================================

async def admin_manual_checkins_start(message: types.Message, state: FSMContext):
    """Начинает диалог обработки ручных заявок (только для админов)."""
    
    # Проверка прав админа
    if message.from_user.id not in config.ADMIN_USERS:
        await message.answer("❌ Эта команда доступна только администраторам.")
        return
    
    pending_requests = get_pending_manual_checkin_requests()
    
    if not pending_requests:
        await message.answer(
            "✅ На данный момент нет ожидающих заявок на ручную отметку.",
            reply_markup=get_timesheet_menu()
        )
        return
    
    # Формируем список заявок
    keyboard = []
    message_lines = ["<b>Ожидающие заявки на ручную отметку:</b>\n"]
    
    for idx, req in enumerate(pending_requests, 1):
        display_name = req.get('application_full_name') or f"@{req.get('username', 'N/A')}"
        
        try:
            time_obj = datetime.strptime(req['requested_checkin_time'], '%Y-%m-%d %H:%M:%S')
            time_str = time_obj.strftime('%d.%m %H:%M')
        except (TypeError, ValueError):
            time_str = "???"
        
        button_text = f"{idx}. {display_name} на {time_str}"
        keyboard.append([types.InlineKeyboardButton(
            text=button_text,
            callback_data=f"admin_manual_req_{req['request_id']}"
        )])
    
    # Кнопки действий
    keyboard.append([types.InlineKeyboardButton(
        text="✅ Принять все",
        callback_data="admin_manual_approve_all"
    )])
    keyboard.append([types.InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="admin_manual_cancel"
    )])
    
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        "\n".join(message_lines),
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    await BotStates.admin_manual_list.set()


async def admin_manual_select_request(query: types.CallbackQuery, state: FSMContext):
    """Показывает детали выбранной заявки."""
    await query.answer()
    
    request_id = int(query.data.split('_')[-1])
    req = get_manual_checkin_request_by_id(request_id)
    
    if not req or req['status'] != 'pending':
        await query.edit_message_text(
            "⚠️ Эта заявка уже обработана или не найдена.",
            reply_markup=None
        )
        return
    
    # Сохраняем в контекст
    await state.update_data(current_manual_request=req)
    
    display_name = req.get('application_full_name') or f"@{req.get('username', 'N/A')}"
    
    try:
        naive_dt = datetime.strptime(req['requested_checkin_time'], '%Y-%m-%d %H:%M:%S')
        display_time = naive_dt.strftime('%d.%m.%Y в %H:%M')
    except (TypeError, ValueError):
        display_time = "Ошибка формата"
    
    message_text = (
        f"<b>Рассмотрение заявки ID: {req['request_id']}</b>\n\n"
        f"<b>Сотрудник:</b> {display_name}\n"
        f"<b>Сектор:</b> {req.get('application_department') or 'Не указан'}\n"
        f"<b>Запрошенное время (МСК):</b> {display_time}\n\n"
        "Выберите действие:"
    )
    
    keyboard = [
        [types.InlineKeyboardButton("✅ Одобрить как есть", callback_data=f"admin_manual_approve_{req['request_id']}")],
        [types.InlineKeyboardButton("🕒 Изменить время", callback_data=f"admin_manual_change_{req['request_id']}")],
        [types.InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_manual_reject_{req['request_id']}")],
        [types.InlineKeyboardButton("« Назад к списку", callback_data="admin_manual_back")]
    ]
    
    await query.edit_message_text(
        message_text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await BotStates.admin_manual_process.set()


async def admin_manual_approve_as_is(query: types.CallbackQuery, state: FSMContext):
    """Одобряет заявку с исходным временем."""
    await query.answer()
    
    data = await state.get_data()
    req = data.get('current_manual_request')
    
    if not req:
        await query.edit_message_text("❌ Ошибка: данные заявки не найдены.")
        await state.finish()
        return
    
    # Парсим время
    requested_time_str = req['requested_checkin_time']
    naive_dt = datetime.strptime(requested_time_str, '%Y-%m-%d %H:%M:%S')
    moscow_dt = MOSCOW_TZ.localize(naive_dt)
    
    # Одобряем
    success = approve_manual_checkin_request(
        request_id=req['request_id'],
        admin_id=query.from_user.id,
        final_checkin_time_local=moscow_dt,
        user_id=req['user_id'],
        user_sector_key=req.get('application_department', 'unknown')
    )
    
    if success:
        display_name = req.get('application_full_name') or f"ID {req['user_id']}"
        await query.edit_message_text(
            f"✅ Заявка от <b>{display_name}</b> одобрена!\n"
            f"Время: {moscow_dt.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML"
        )
        
        # Уведомляем пользователя
        try:
            await query.bot.send_message(
                chat_id=req['user_id'],
                text=f"✅ Ваша заявка на ручную отметку одобрена.\n"
                     f"Установленное время: {moscow_dt.strftime('%d.%m.%Y %H:%M')}"
            )
        except Exception:
            pass
    else:
        await query.edit_message_text("❌ Ошибка при одобрении заявки.")
    
    await state.finish()


async def admin_manual_change_time(query: types.CallbackQuery, state: FSMContext):
    """Запрашивает новое время для заявки."""
    await query.answer()
    
    data = await state.get_data()
    req = data.get('current_manual_request')
    
    display_name = req.get('application_full_name') or f"ID {req['user_id']}"
    
    await query.edit_message_text(
        f"Введите новое время для <b>{display_name}</b> в формате:\n"
        f"<code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n\n"
        f"Например: <code>27.10.2025 09:00</code>",
        parse_mode="HTML"
    )
    await BotStates.admin_manual_enter_time.set()


async def admin_manual_receive_new_time(message: types.Message, state: FSMContext):
    """Обрабатывает новое время от админа."""
    user_input = message.text
    
    try:
        new_time_dt = datetime.strptime(user_input, '%d.%m.%Y %H:%M')
        aware_new_time = MOSCOW_TZ.localize(new_time_dt)
        
        # Сохраняем в контекст
        await state.update_data(new_time_from_admin=aware_new_time)
        
        data = await state.get_data()
        req = data.get('current_manual_request')
        display_name = req.get('application_full_name') or f"ID {req['user_id']}"
        
        keyboard = [
            [types.InlineKeyboardButton("✅ Да", callback_data="admin_manual_confirm_yes")],
            [types.InlineKeyboardButton("❌ Нет", callback_data="admin_manual_confirm_no")]
        ]
        
        await message.answer(
            f"Одобрить заявку для <b>{display_name}</b> "
            f"с новым временем <b>{aware_new_time.strftime('%d.%m.%Y %H:%M')}</b>?",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode="HTML"
        )
        await BotStates.admin_manual_confirm.set()
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Используйте: <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>",
            parse_mode="HTML"
        )


async def admin_manual_confirm(query: types.CallbackQuery, state: FSMContext):
    """Финальное подтверждение действия."""
    await query.answer()
    
    data = await state.get_data()
    req = data.get('current_manual_request')
    
    if query.data == "admin_manual_confirm_yes":
        new_time = data.get('new_time_from_admin')
        
        success = approve_manual_checkin_request(
            request_id=req['request_id'],
            admin_id=query.from_user.id,
            final_checkin_time_local=new_time,
            user_id=req['user_id'],
            user_sector_key=req.get('application_department', 'unknown')
        )
        
        if success:
            display_name = req.get('application_full_name') or f"ID {req['user_id']}"
            await query.edit_message_text(
                f"✅ Заявка от <b>{display_name}</b> одобрена с новым временем!\n"
                f"Время: {new_time.strftime('%d.%m.%Y %H:%M')}",
                parse_mode="HTML"
            )
            
            try:
                await query.bot.send_message(
                    chat_id=req['user_id'],
                    text=f"✅ Ваша заявка одобрена.\nВремя: {new_time.strftime('%d.%m.%Y %H:%M')}"
                )
            except Exception:
                pass
        else:
            await query.edit_message_text("❌ Ошибка при одобрении.")
    else:
        await query.message.delete()
        await query.message.answer("Действие отменено.")
    
    await state.finish()


async def admin_manual_reject(query: types.CallbackQuery, state: FSMContext):
    """Отклоняет заявку."""
    await query.answer()
    
    data = await state.get_data()
    req = data.get('current_manual_request')
    
    success = reject_manual_checkin_request(
        request_id=req['request_id'],
        admin_id=query.from_user.id
    )
    
    if success:
        display_name = req.get('application_full_name') or f"ID {req['user_id']}"
        await query.edit_message_text(
            f"❌ Заявка от <b>{display_name}</b> отклонена.",
            parse_mode="HTML"
        )
        
        try:
            await query.bot.send_message(
                chat_id=req['user_id'],
                text="❌ Ваша заявка на ручную отметку была отклонена."
            )
        except Exception:
            pass
    else:
        await query.edit_message_text("❌ Ошибка при отклонении.")
    
    await state.finish()


async def admin_manual_approve_all(query: types.CallbackQuery, state: FSMContext):
    """Одобряет все ожидающие заявки."""
    await query.answer(text="Начинаю массовое одобрение...", cache_time=2)
    
    approved_list, failed_count = approve_all_pending_manual_checkins(query.from_user.id)
    approved_count = len(approved_list)
    
    # Отправляем уведомления
    sent_notifications = 0
    for approval_data in approved_list:
        try:
            user_id = approval_data['user_id']
            naive_dt = datetime.strptime(approval_data['checkin_time_str'], '%Y-%m-%d %H:%M:%S')
            time_str = naive_dt.strftime('%d.%m.%Y %H:%M')
            
            await query.bot.send_message(
                chat_id=user_id,
                text=f"✅ Ваша заявка одобрена. Время: {time_str}"
            )
            sent_notifications += 1
        except Exception:
            pass
    
    response_text = (
        f"✅ Массовое одобрение завершено!\n\n"
        f"Успешно: {approved_count} шт.\n"
        f"Уведомлений: {sent_notifications} шт.\n"
        f"Ошибок: {failed_count} шт."
    )
    
    await query.edit_message_text(text=response_text)
    await state.finish()


async def admin_manual_back(query: types.CallbackQuery, state: FSMContext):
    """Возврат к списку заявок."""
    await query.answer()
    # Просто вызываем стартовую функцию заново
    await admin_manual_checkins_start(query.message, state)


async def admin_manual_cancel(query: types.CallbackQuery, state: FSMContext):
    """Отменяет диалог."""
    await query.answer()
    await query.edit_message_text("❌ Диалог отменен.")
    await state.finish()


# ============================================================================
# РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
# ============================================================================

def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков табеля"""
    
    # Меню табеля
    dp.register_message_handler(
        timesheet_menu_handler,
        state=BotStates.timesheet_menu
    )
    
    # Получение геолокации
    dp.register_message_handler(
        location_handler,
        content_types=types.ContentType.LOCATION,
        state=BotStates.timesheet_waiting_location
    )
    
    # === РУЧНЫЕ ЗАЯВКИ: ПОЛЬЗОВАТЕЛЬ ===
    dp.register_message_handler(
        process_manual_checkin_time,
        state=BotStates.timesheet_manual_request_time
    )
    
    # === РУЧНЫЕ ЗАЯВКИ: АДМИН ===
    # Команда запуска
    from aiogram.dispatcher.filters import Command
    dp.register_message_handler(
        admin_manual_checkins_start,
        Command("admin_manual_checkins"),
        state="*"
    )
    
    # Callback handlers
    dp.register_callback_query_handler(
        admin_manual_select_request,
        lambda c: c.data.startswith("admin_manual_req_"),
        state=BotStates.admin_manual_list
    )
    
    dp.register_callback_query_handler(
        admin_manual_approve_as_is,
        lambda c: c.data.startswith("admin_manual_approve_"),
        state=BotStates.admin_manual_process
    )
    
    dp.register_callback_query_handler(
        admin_manual_change_time,
        lambda c: c.data.startswith("admin_manual_change_"),
        state=BotStates.admin_manual_process
    )
    
    dp.register_callback_query_handler(
        admin_manual_reject,
        lambda c: c.data.startswith("admin_manual_reject_"),
        state=BotStates.admin_manual_process
    )
    
    dp.register_callback_query_handler(
        admin_manual_approve_all,
        lambda c: c.data == "admin_manual_approve_all",
        state=BotStates.admin_manual_list
    )
    
    dp.register_callback_query_handler(
        admin_manual_back,
        lambda c: c.data == "admin_manual_back",
        state=BotStates.admin_manual_process
    )
    
    dp.register_callback_query_handler(
        admin_manual_cancel,
        lambda c: c.data == "admin_manual_cancel",
        state="*"
    )
    
    # Ввод нового времени админом
    dp.register_message_handler(
        admin_manual_receive_new_time,
        state=BotStates.admin_manual_enter_time
    )
    
    # Подтверждение
    dp.register_callback_query_handler(
        admin_manual_confirm,
        lambda c: c.data.startswith("admin_manual_confirm_"),
        state=BotStates.admin_manual_confirm
    )