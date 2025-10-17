from aiogram.dispatcher.filters.state import State, StatesGroup
from keyboards import get_main_menu

class BotStates(StatesGroup):
    """Состояния бота (FSM)"""
    
    # Главное меню
    main_menu = State()
    
    # AI-помощник
    ai_menu = State()
    ai_asking = State()
    
    # Справочник
    handbook_menu = State()
    handbook_uploading = State()          # Загрузка документа
    handbook_waiting_file = State()       # Ожидание файла
    handbook_creating_category = State()  # Создание категории
    
    # Табель
    timesheet_menu = State()
    
    # Тех.специалист
    tech_menu = State()