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
            "Задавай любые вопросы!",
            parse_mode="HTML",
            reply_markup=get_ai_menu()
        )
        await BotStates.ai_menu.set()
    
    elif text == "📚 Справочник":
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
            "Выберите действие:",
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
    
    # Тех.специалист
    dp.register_message_handler(tech_menu_handler, state=BotStates.tech_menu)