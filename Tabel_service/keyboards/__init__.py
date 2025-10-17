"""
Клавиатуры для табеля.
"""
from .common import (
    get_location_keyboard,
    remove_keyboard,
)
from .admin import (
    get_department_selection_keyboard,
    get_sector_selection_keyboard,
    get_period_selection_keyboard,
    get_files_keyboard,
    get_pagination_keyboard,
)

__all__ = [
    # Common
    'get_location_keyboard',
    'remove_keyboard',
    
    # Admin
    'get_department_selection_keyboard',
    'get_sector_selection_keyboard',
    'get_period_selection_keyboard',
    'get_files_keyboard',
    'get_pagination_keyboard',
]