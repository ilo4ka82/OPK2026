"""
Общие клавиатуры для табеля.
"""
from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


def get_location_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура с кнопкой отправки геолокации.
    
    Returns:
        ReplyKeyboardMarkup с кнопкой геолокации
    """
    location_button = KeyboardButton(
        text="📍 Отправить мою геолокацию",
        request_location=True
    )
    keyboard = ReplyKeyboardMarkup(
        [[location_button]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard


def remove_keyboard() -> ReplyKeyboardRemove:
    """
    Убирает клавиатуру.
    
    Returns:
        ReplyKeyboardRemove объект
    """
    return ReplyKeyboardRemove()