"""
Константы для табеля.
"""

# Геозона офиса (координаты)
THE_OFFICE_ZONE = {
    "min_latitude": 55.753988,
    "max_latitude": 55.756340,
    "min_longitude": 37.710915,
    "max_longitude": 37.716277
}

# Нормы рабочего времени по секторам (часов в неделю)
SECTOR_WEEKLY_NORMS = {
    "СС": 40,
    "ВИ": 40,
    "ОП": 40,
    "DEFAULT_NORM": 40
}

# Расписание работы секторов
SECTOR_SCHEDULES = {
    'ОП': {'start_hour': 9, 'end_hour': 18},
    'ВИ': {'start_hour': 9, 'end_hour': 18},
    'СС': {'start_hour': 10, 'end_hour': 19},
}

# Предопределенные секторы для выбора
PREDEFINED_SECTORS = ["Сектор СС", "Сектор ВИ", "Сектор ОП"]

# Настройки пагинации
ITEMS_PER_PAGE = 7
SESSIONS_PER_PAGE = 5

# Настройки геолокации
MAX_LOCATION_AGE_SECONDS = 300  # 5 минут

# Московский часовой пояс
MOSCOW_TIMEZONE = 'Europe/Moscow'