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
    
    # Табель - базовый функционал
    timesheet_menu = State()
    timesheet_waiting_location = State()
    
    # Табель - ручные заявки (пользователь)
    timesheet_manual_request_time = State()
    
    # Табель - ручные заявки (админ)
    admin_manual_list = State()
    admin_manual_process = State()
    admin_manual_enter_time = State()
    admin_manual_confirm = State()
    
    # Тех.специалист
    tech_menu = State()