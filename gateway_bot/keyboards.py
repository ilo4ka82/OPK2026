import os
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from config import config

def get_main_menu():
    """Главное меню"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    
    keyboard.row(
        KeyboardButton("🤖 AI-помощник"),
        KeyboardButton("📚 Справочник")
    )
    keyboard.row(
        KeyboardButton("⏰ Табель"),
        KeyboardButton("🔧 Тех.специалист")
    )
    
    return keyboard

def get_back_button():
    """Кнопка назад в главное меню"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("◀️ Главное меню"))
    return keyboard

def get_ai_menu():
    """Меню AI-помощника"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    
    keyboard.row(
        KeyboardButton("❓ Задать вопрос")
    )
    keyboard.row(
        KeyboardButton("🧹 Очистить историю"),
        KeyboardButton("📊 Статистика")
    )
    keyboard.add(KeyboardButton("◀️ Главное меню"))
    
    return keyboard

def get_timesheet_menu():
    """Меню табеля"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    
    keyboard.row(
        KeyboardButton("▶️ Начать смену"),
        KeyboardButton("⏹️ Закончить смену")
    )
    keyboard.row(
        KeyboardButton("📊 Моя статистика")
    )
    keyboard.add(KeyboardButton("◀️ Главное меню"))
    
    return keyboard

def get_tech_menu():
    """Меню тех.специалиста"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    
    keyboard.row(
        KeyboardButton("📝 Создать отчет"),
        KeyboardButton("🔄 Обновить данные")
    )
    keyboard.row(
        KeyboardButton("⚙️ Скрипты"),
        KeyboardButton("📁 Файлы")
    )
    keyboard.add(KeyboardButton("◀️ Главное меню"))
    
    return keyboard

def get_handbook_menu(is_admin=False):
    """Меню справочника (разное для админа и пользователя)"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    
    # Динамически получаем категории из папок
    categories = get_categories()
    
    # Показываем категории (по 2 в ряд)
    category_buttons = []
    for category_id, category_name in categories.items():
        category_buttons.append(KeyboardButton(category_name))
    
    # Разбиваем по 2 кнопки в ряд
    for i in range(0, len(category_buttons), 2):
        if i + 1 < len(category_buttons):
            keyboard.row(category_buttons[i], category_buttons[i + 1])
        else:
            keyboard.add(category_buttons[i])
    
    # Кнопки для админа
    if is_admin:
        keyboard.row(
            KeyboardButton("⬆️ Загрузить документ"),
            KeyboardButton("➕ Создать категорию")
        )
    
    keyboard.add(KeyboardButton("◀️ Главное меню"))
    
    return keyboard

def get_categories():
    """Получить список категорий из папок"""
    docs_dir = config.DOCUMENTS_DIR
    
    if not os.path.exists(docs_dir):
        os.makedirs(docs_dir, exist_ok=True)
    
    # Читаем красивые имена из файла
    config_file = os.path.join(docs_dir, "_category_names.txt")
    custom_names = {}
    
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    custom_names[key] = value
    
    categories = {}
    
    # Сканируем папки в documents/
    for folder in os.listdir(docs_dir):
        folder_path = os.path.join(docs_dir, folder)
        
        # Пропускаем служебные файлы
        if folder.startswith("_"):
            continue
        
        if os.path.isdir(folder_path):
            # Если есть кастомное имя - используем его
            if folder in custom_names:
                display_name = f"📁 {custom_names[folder]}"
            # Иначе берем из дефолтного конфига
            elif folder in config.DOCUMENT_CATEGORIES:
                display_name = config.DOCUMENT_CATEGORIES[folder]
            # Иначе делаем из названия папки
            else:
                display_name = f"📁 {folder.replace('_', ' ').title()}"
            
            categories[folder] = display_name
    
    # Если категорий нет - показываем дефолтные
    if not categories:
        categories = {
            "pravila": "📄 Правила приема",
            "metodichki": "📖 Методички",
        }
    
    return categories

def get_category_keyboard_inline():
    """Клавиатура выбора категории для загрузки (inline)"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    categories = get_categories()
    
    buttons = []
    for category_id, category_name in categories.items():
        buttons.append(
            InlineKeyboardButton(
                category_name, 
                callback_data=f"upload_cat_{category_id}"
            )
        )
    
    # Разбиваем по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.row(buttons[i], buttons[i + 1])
        else:
            keyboard.add(buttons[i])
    
    keyboard.add(
        InlineKeyboardButton("❌ Отмена", callback_data="upload_cat_cancel")
    )
    
    return keyboard

def get_files_keyboard(category: str):
    """Клавиатура со списком файлов в категории (inline)"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    category_dir = os.path.join(config.DOCUMENTS_DIR, category)
    
    if not os.path.exists(category_dir):
        return keyboard
    
    # Получаем файлы
    files = sorted([
        f for f in os.listdir(category_dir) 
        if os.path.isfile(os.path.join(category_dir, f))
    ])
    
    # Добавляем кнопку для каждого файла
    for idx, filename in enumerate(files):
        # Обрезаем длинные имена для отображения
        display_name = filename
        if len(display_name) > 40:
            display_name = display_name[:37] + "..."
        
        # ИСПРАВЛЕНО: используем индекс вместо полного имени
        keyboard.add(
            InlineKeyboardButton(
                f"📄 {display_name}",
                callback_data=f"file_{category}_{idx}"  # ✅ Короткий callback_data!
            )
        )
    
    keyboard.add(
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_handbook")
    )
    
    return keyboard

