from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext

from config import config  
from keyboards import (  
    get_main_menu, 
    get_ai_menu, 
    get_handbook_menu,
    get_timesheet_menu,
    get_tech_menu
)
from states import BotStates
from handlers.handbook import is_admin

async def reset_state_handler(message: types.Message, state: FSMContext):
    """
    Обработчик на случай потери состояния после перезапуска.
    Сбрасывает state и возвращает в главное меню.
    """
    await state.finish()
    
    await message.answer(
        "🔄 Бот был перезапущен.\n"
        "Возвращаю вас в главное меню...",
        reply_markup=get_main_menu()
    )
    
    await BotStates.main_menu.set()

async def check_access(message: types.Message) -> bool:
    """Проверка доступа пользователя"""
    user_id = message.from_user.id
    
    if config.ALLOW_ALL:
        return True
    
    if user_id not in config.ALLOWED_USERS:
        await message.answer(
            "❌ У вас нет доступа к этому боту.\n"
            "Обратитесь к администратору."
        )
        return False
    
    return True

async def cmd_start(message: types.Message, state: FSMContext):
    """Команда /start"""
    
    # Проверка доступа
    if not await check_access(message):
        return
    
    user_name = message.from_user.first_name
    
    await message.answer(
        f"👋 Привет, <b>{user_name}</b>!\n\n"
        f"Я — помощник приемной комиссии.\n"
        f"Выбери нужный раздел:",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )
    
    await BotStates.main_menu.set()

async def main_menu_handler(message: types.Message, state: FSMContext):
    """Обработчик главного меню"""
    
    text = message.text
    user_id = message.from_user.id
    
    if text == "🤖 AI-помощник":
        await message.answer(
            "🤖 <b>AI-помощник</b>\n\n"
            "Я помогу найти информацию в документах приемной комиссии.\n"
            "Задавай любые вопросы!\n\n"
            "<i>⚠️ AI пока в разработке - это заглушка</i>",
            parse_mode="HTML",
            reply_markup=get_ai_menu()
        )
        await BotStates.ai_menu.set()
    
    elif text == "📚 Справочник":
        # Проверяем права админf
        admin = is_admin(user_id)
        
        admin_text = ""
        if admin:
            admin_text = "\n\n👨‍💼 <b>Режим администратора</b>\nВы можете загружать документы"
        
        await message.answer(
            f"📚 <b>Справочное бюро</b>\n\n"
            f"Здесь хранятся все документы и методички приемной комиссии.{admin_text}",
            parse_mode="HTML",
            reply_markup=get_handbook_menu(admin)
        )
        await BotStates.handbook_menu.set()
    
    elif text == "⏰ Табель":
        await message.answer(
            "⏰ <b>Табель учета времени</b>\n\n"
            "🚧 <i>Здесь будет переписанный табель с другого бота</i>\n\n"
            "Функционал:\n"
            "• Начало/конец рабочего дня\n"
            "• Перерывы\n"
            "• Статистика времени\n"
            "• Отчеты",
            parse_mode="HTML",
            reply_markup=get_timesheet_menu()
        )
        await BotStates.timesheet_menu.set()
    
    elif text == "🔧 Тех.специалист":
        await message.answer(
            "🔧 <b>Технический специалист</b>\n\n"
            "🚧 <i>Здесь будут функции:</i>\n\n"
            "• Автоматизация задач (код есть в другом боте)\n"
            "• Новая задача (допишешь позже)\n"
            "• Генерация отчетов\n"
            "• Служебные скрипты",
            parse_mode="HTML",
            reply_markup=get_tech_menu()
        )
        await BotStates.tech_menu.set()
    
    else:
        await message.answer(
            "❓ Используй кнопки меню",
            reply_markup=get_main_menu()
        )

async def back_to_main(message: types.Message, state: FSMContext):
    """Возврат в главное меню"""
    await message.answer(
        "🏠 <b>Главное меню</b>",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )
    await BotStates.main_menu.set()

# ===== AI-помощник (заглушки) =====

async def ai_menu_handler(message: types.Message, state: FSMContext):
    """Обработчик меню AI"""
    
    text = message.text
    
    if text == "❓ Задать вопрос":
        await message.answer(
            "✏️ Задай свой вопрос текстом:",
            reply_markup=get_ai_menu()
        )
        await BotStates.ai_asking.set()
    
    elif text == "🧹 Очистить историю":
        await message.answer(
            "✅ История диалога очищена!",
            reply_markup=get_ai_menu()
        )
    
    elif text == "📊 Статистика":
        await message.answer(
            "📊 <b>Твоя статистика:</b>\n\n"
            "Всего вопросов: 0\n"
            "Последний вопрос: —\n\n"
            "<i>⚠️ Статистика пока не работает</i>",
            parse_mode="HTML",
            reply_markup=get_ai_menu()
        )
    
    else:
        await message.answer(
            "Используй кнопки меню",
            reply_markup=get_ai_menu()
        )

async def ai_question_handler(message: types.Message, state: FSMContext):
    """Обработка вопроса к AI"""
    
    question = message.text
    
    # Пока заглушка
    await message.answer(
        f"❓ Твой вопрос:\n<i>{question}</i>\n\n"
        f"🤖 <b>Ответ:</b>\n"
        f"[AI-помощник пока не подключен]\n\n"
        f"Скоро здесь будет умный ответ на основе документов!",
        parse_mode="HTML",
        reply_markup=get_ai_menu()
    )
    
    await BotStates.ai_menu.set()

# ===== Табель (заглушки) =====

async def timesheet_menu_handler(message: types.Message, state: FSMContext):
    """Обработчик меню табеля"""
    
    await message.answer(
        "⏰ <b>Табель учета времени</b>\n\n"
        "🚧 <i>Здесь будет переписанный табель с другого бота</i>\n\n"
        "Функционал:\n"
        "• Начало/конец рабочего дня\n"
        "• Перерывы\n"
        "• Статистика времени\n"
        "• Отчеты",
        parse_mode="HTML",
        reply_markup=get_timesheet_menu()
    )

# ===== Тех.специалист (заглушки) =====

async def tech_menu_handler(message: types.Message, state: FSMContext):
    """Обработчик меню тех.специалиста"""
    
    await message.answer(
        "🔧 <b>Технический специалист</b>\n\n"
        "🚧 <i>Здесь будут функции:</i>\n\n"
        "• Автоматизация задач (код есть в другом боте)\n"
        "• Новая задача (допишешь позже)\n"
        "• Генерация отчетов\n"
        "• Служебные скрипты",
        parse_mode="HTML",
        reply_markup=get_tech_menu()
    )

def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков"""
    
    # /start
    dp.register_message_handler(cmd_start, commands=['start'], state="*")
    
    # Главное меню
    dp.register_message_handler(main_menu_handler, state=BotStates.main_menu)
    
    # Кнопка "Назад"
    dp.register_message_handler(
        back_to_main,
        lambda msg: msg.text == "◀️ Главное меню",
        state="*"
    )
    
    # AI-помощник
    dp.register_message_handler(ai_menu_handler, state=BotStates.ai_menu)
    dp.register_message_handler(ai_question_handler, state=BotStates.ai_asking)
    
    # Табель
    dp.register_message_handler(timesheet_menu_handler, state=BotStates.timesheet_menu)
    
    # Тех.специалист
    dp.register_message_handler(tech_menu_handler, state=BotStates.tech_menu)

    dp.register_message_handler(
        reset_state_handler,
        state="*",  # Любое состояние
        content_types=types.ContentType.TEXT
    )