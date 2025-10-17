"""
Админские клавиатуры для табеля.
"""
import math
from typing import List, Optional
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from ..utils import PREDEFINED_SECTORS, ITEMS_PER_PAGE


def get_department_selection_keyboard(departments: List[str]) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора департамента для просмотра кто на смене.
    
    Args:
        departments: Список названий департаментов
        
    Returns:
        InlineKeyboardMarkup с кнопками департаментов
    """
    keyboard = []
    
    for department_name in departments:
        keyboard.append([
            InlineKeyboardButton(
                f"Департамент: {department_name}",
                callback_data=f"on_shift_dept:{department_name}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("Показать всех", callback_data="on_shift_dept:ALL")
    ])
    keyboard.append([
        InlineKeyboardButton("Отмена", callback_data="on_shift_cancel")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_sector_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура выбора сектора для экспорта.
    
    Returns:
        InlineKeyboardMarkup с кнопками секторов
    """
    keyboard = [
        [InlineKeyboardButton("Все секторы", callback_data="export_sector_ALL")]
    ]
    
    for sector_name in PREDEFINED_SECTORS:
        parts = sector_name.split()
        sector_key = parts[-1].upper() if len(parts) > 1 else sector_name.upper()
        
        keyboard.append([
            InlineKeyboardButton(sector_name, callback_data=f"export_sector_{sector_key}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("❌ Отменить экспорт", callback_data="export_cancel_dialog")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_period_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура выбора периода для экспорта.
    
    Returns:
        InlineKeyboardMarkup с кнопками периодов
    """
    keyboard = [
        [InlineKeyboardButton("Сегодня", callback_data="export_period_today")],
        [InlineKeyboardButton("Вчера", callback_data="export_period_yesterday")],
        [InlineKeyboardButton("Эта неделя", callback_data="export_period_this_week")],
        [InlineKeyboardButton("Прошлая неделя", callback_data="export_period_last_week")],
        [InlineKeyboardButton("Этот месяц", callback_data="export_period_this_month")],
        [InlineKeyboardButton("Прошлый месяц", callback_data="export_period_last_month")],
        [InlineKeyboardButton("🗓️ Произвольный период", callback_data="export_period_custom")],
        [InlineKeyboardButton("⬅️ Назад (к выбору сектора)", callback_data="export_back_to_sector_selection")],
        [InlineKeyboardButton("❌ Отменить экспорт", callback_data="export_cancel_dialog")]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_files_keyboard(category: str, files: List[str]) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком файлов (для будущего использования).
    
    Args:
        category: Категория файлов
        files: Список названий файлов
        
    Returns:
        InlineKeyboardMarkup с кнопками файлов
    """
    keyboard = []
    
    for filename in files:
        display_name = filename
        if len(display_name) > 40:
            display_name = display_name[:37] + "..."
        
        keyboard.append([
            InlineKeyboardButton(
                f"📄 {display_name}",
                callback_data=f"file_{category}_{filename}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_list")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_pagination_keyboard(
    current_page: int,
    total_items: int,
    items_per_page: int = ITEMS_PER_PAGE,
    focused_user_id: Optional[int] = None
) -> InlineKeyboardMarkup:
    """
    Клавиатура с пагинацией для списков.
    
    Args:
        current_page: Текущая страница (начиная с 1)
        total_items: Общее количество элементов
        items_per_page: Элементов на странице
        focused_user_id: ID пользователя для фокуса (опционально)
        
    Returns:
        InlineKeyboardMarkup с кнопками навигации
    """
    total_pages = math.ceil(total_items / items_per_page)
    keyboard = []
    
    pagination_row = []
    focused_id_for_callback = focused_user_id if focused_user_id else 0
    
    if current_page > 1:
        pagination_row.append(
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=f"paginate_list:{current_page-1}:{focused_id_for_callback}"
            )
        )
    
    # Кнопка с номером страницы (некликабельная)
    pagination_row.append(
        InlineKeyboardButton(
            f"Стр. {current_page}/{total_pages}",
            callback_data="_"
        )
    )
    
    if current_page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(
                "Вперед ➡️",
                callback_data=f"paginate_list:{current_page+1}:{focused_id_for_callback}"
            )
        )
    
    if pagination_row:
        keyboard.append(pagination_row)
    
    return InlineKeyboardMarkup(keyboard)


def get_category_selection_keyboard(categories: dict) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора категории (универсальная).
    
    Args:
        categories: Словарь {category_key: category_display_name}
        
    Returns:
        InlineKeyboardMarkup с кнопками категорий
    """
    keyboard = []
    
    buttons = []
    for category_id, category_name in categories.items():
        buttons.append(
            InlineKeyboardButton(
                category_name,
                callback_data=f"select_cat_{category_id}"
            )
        )
    
    # Разбиваем по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.append([buttons[i], buttons[i + 1]])
        else:
            keyboard.append([buttons[i]])
    
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="select_cat_cancel")
    ])
    
    return InlineKeyboardMarkup(keyboard)
