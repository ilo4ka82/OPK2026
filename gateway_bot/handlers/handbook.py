import os
from aiogram import types, Dispatcher  
from aiogram.dispatcher import FSMContext
from config import config
from keyboards import (
    get_handbook_menu, 
    get_category_keyboard_inline,
    get_files_keyboard,
    get_categories
)
from states import BotStates

def is_admin(user_id: int) -> bool:
    """Проверка: является ли пользователь админом"""
    return user_id in config.ADMIN_USERS

async def handbook_menu_handler(message: types.Message, state: FSMContext):
    """Обработчик меню справочника"""
    
    text = message.text
    user_id = message.from_user.id
    admin = is_admin(user_id)
    
    # ===== СОЗДАНИЕ КАТЕГОРИИ (только для админа) =====
    
    if text == "➕ Создать категорию":
        if not admin:
            await message.answer(
                "❌ У вас нет прав для создания категорий",
                reply_markup=get_handbook_menu(admin)
            )
            return
        
        await message.answer(
            "📝 <b>Создание новой категории</b>\n\n"
            "Введи название категории на английском (без пробелов):\n"
            "Например: <code>diplomy</code>, <code>lgoty</code>, <code>bvi</code>\n\n"
            "<i>Для отмены напиши: отмена</i>",
            parse_mode="HTML"
        )
        await BotStates.handbook_creating_category.set()
        return
    
    # ===== ЗАГРУЗКА ДОКУМЕНТА (только для админа) =====
    
    elif text == "⬆️ Загрузить документ":
        if not admin:
            await message.answer(
                "❌ У вас нет прав для загрузки документов",
                reply_markup=get_handbook_menu(admin)
            )
            return
        
        await message.answer(
            "📂 <b>Загрузка документа</b>\n\n"
            "Выбери категорию для документа:",
            parse_mode="HTML",
            reply_markup=get_category_keyboard_inline()
        )
        await BotStates.handbook_uploading.set()
        return
    
    # ===== ПРОСМОТР КАТЕГОРИЙ =====
    
    # Проверяем, является ли текст названием категории
    categories = get_categories()
    
    for category_id, category_name in categories.items():
        if text == category_name:
            await show_category_files(message, category_id, admin)
            return
    
    # Если не распознали команду
    await message.answer(
        "❓ Выбери категорию из меню",
        reply_markup=get_handbook_menu(admin)
    )

async def show_category_files(message: types.Message, category: str, admin: bool):
    """Показать список файлов в категории"""
    
    category_dir = os.path.join(config.DOCUMENTS_DIR, category)
    
    # Проверяем существование папки
    if not os.path.exists(category_dir):
        os.makedirs(category_dir, exist_ok=True)
    
    # Получаем список файлов
    files = sorted([
        f for f in os.listdir(category_dir) 
        if os.path.isfile(os.path.join(category_dir, f))
    ])
    
    categories = get_categories()
    category_name = categories.get(category, f"📁 {category}")
    
    if not files:
        await message.answer(
            f"📂 <b>{category_name}</b>\n\n"
            f"В этой категории пока нет документов.",
            parse_mode="HTML",
            reply_markup=get_handbook_menu(admin)
        )
        return
    
    # Показываем список файлов с кнопками
    await message.answer(
        f"📂 <b>{category_name}</b>\n\n"
        f"📄 Файлов: {len(files)}\n\n"
        f"Выбери файл для скачивания:",
        parse_mode="HTML",
        reply_markup=get_files_keyboard(category)
    )

# ===== СОЗДАНИЕ КАТЕГОРИИ =====

async def create_category_handler(message: types.Message, state: FSMContext):
    """Обработка создания новой категории"""
    
    user_id = message.from_user.id
    admin = is_admin(user_id)
    
    if not admin:
        await message.answer("❌ У вас нет прав")
        await BotStates.handbook_menu.set()
        return
    
    # Проверка на отмену
    if message.text and message.text.lower() in ["отмена", "отменить", "cancel"]:
        await message.answer(
            "❌ Создание категории отменено",
            reply_markup=get_handbook_menu(admin)
        )
        await BotStates.handbook_menu.set()
        return
    
    # Получаем данные из state
    data = await state.get_data()
    
    # Если еще не спрашивали английское название
    if not data.get("category_id"):
        category_id = message.text.strip().lower()
        
        # Валидация имени
        if not category_id.replace("_", "").replace("-", "").isalnum():
            await message.answer(
                "❌ Неправильное название!\n\n"
                "Используй только:\n"
                "• Английские буквы (a-z)\n"
                "• Цифры (0-9)\n"
                "• Подчеркивание (_) или дефис (-)\n\n"
                "Попробуй еще раз:"
            )
            return
        
        # Проверяем что папка не существует
        category_dir = os.path.join(config.DOCUMENTS_DIR, category_id)
        
        if os.path.exists(category_dir):
            await message.answer(
                f"⚠️ Категория <code>{category_id}</code> уже существует!\n\n"
                f"Придумай другое название:",
                parse_mode="HTML"
            )
            return
        
        # Сохраняем category_id и спрашиваем русское название
        await state.update_data(category_id=category_id)
        
        await message.answer(
            f"✅ Системное название: <code>{category_id}</code>\n\n"
            f"📝 Теперь введи <b>красивое название</b> (как будет показываться пользователям):\n"
            f"Например: <i>Пенис и вагина</i>, <i>Документы для поступления</i>\n\n"
            f"<i>Для отмены напиши: отмена</i>",
            parse_mode="HTML"
        )
        return
    
    # Если уже есть category_id - значит вводим display_name
    category_id = data.get("category_id")
    display_name = message.text.strip()
    
    if not display_name:
        await message.answer("❌ Название не может быть пустым!\nПопробуй еще раз:")
        return
    
    # Создаем папку
    category_dir = os.path.join(config.DOCUMENTS_DIR, category_id)
    
    try:
        os.makedirs(category_dir, exist_ok=True)
        
        # Сохраняем красивое имя в config (в файл)
        config_file = os.path.join(config.DOCUMENTS_DIR, "_category_names.txt")
        
        # Читаем существующие
        category_names = {}
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        category_names[key] = value
        
        # Добавляем новую
        category_names[category_id] = display_name
        
        # Сохраняем
        with open(config_file, 'w', encoding='utf-8') as f:
            for key, value in category_names.items():
                f.write(f"{key}={value}\n")
        
        await message.answer(
            f"✅ <b>Категория создана!</b>\n\n"
            f"📁 Системное название: <code>{category_id}</code>\n"
            f"📝 Отображается как: <b>{display_name}</b>\n"
            f"📂 Путь: <code>{category_dir}</code>\n\n"
            f"Теперь можешь загружать в неё документы!",
            parse_mode="HTML",
            reply_markup=get_handbook_menu(admin)
        )
        
        # Очищаем state
        await state.finish()
        await BotStates.handbook_menu.set()
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при создании категории: {e}",
            reply_markup=get_handbook_menu(admin)
        )
        await state.finish()
        await BotStates.handbook_menu.set()

# ===== ЗАГРУЗКА ДОКУМЕНТОВ =====

async def category_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора категории для загрузки"""
    
    if callback.data == "upload_cat_cancel":
        await callback.message.edit_text("❌ Загрузка отменена")
        await callback.answer()
        
        user_id = callback.from_user.id
        admin = is_admin(user_id)
        
        await callback.message.answer(
            "📚 Справочное бюро",
            reply_markup=get_handbook_menu(admin)
        )
        await BotStates.handbook_menu.set()
        return
    
    category = callback.data.replace("upload_cat_", "")
    
    # Сохраняем категорию в state
    await state.update_data(upload_category=category)
    
    categories = get_categories()
    category_name = categories.get(category, f"📁 {category}")
    
    await callback.message.edit_text(
        f"📂 Категория: <b>{category_name}</b>\n\n"
        f"📎 Теперь отправь документ (PDF, DOCX, TXT, XLS и др.)\n\n"
        f"<i>Для отмены напиши: отмена</i>",
        parse_mode="HTML"
    )
    await callback.answer()
    
    await BotStates.handbook_waiting_file.set()

async def document_upload_handler(message: types.Message, state: FSMContext):
    """Обработка загрузки документа"""
    
    user_id = message.from_user.id
    admin = is_admin(user_id)
    
    if not admin:
        await message.answer("❌ У вас нет прав для загрузки")
        await BotStates.handbook_menu.set()
        return
    
    # Проверка на отмену
    if message.text and message.text.lower() in ["отмена", "отменить", "cancel"]:
        await message.answer(
            "❌ Загрузка отменена",
            reply_markup=get_handbook_menu(admin)
        )
        await BotStates.handbook_menu.set()
        return
    
    # Проверка что это документ
    if not message.document:
        await message.answer(
            "❌ Это не документ.\n"
            "Отправь файл (PDF, DOCX и др.)\n\n"
            "Для отмены напиши: <b>отмена</b>",
            parse_mode="HTML"
        )
        return
    
    # Получаем данные из state
    data = await state.get_data()
    category = data.get("upload_category", "other")
    
    # Создаем папку категории если нет
    category_dir = os.path.join(config.DOCUMENTS_DIR, category)
    os.makedirs(category_dir, exist_ok=True)
    
    # Скачиваем файл
    document = message.document
    file_name = document.file_name
    file_path = os.path.join(category_dir, file_name)
    
    try:
        await document.download(destination_file=file_path)
        
        categories = get_categories()
        category_name = categories.get(category, f"📁 {category}")
        
        await message.answer(
            f"✅ <b>Документ загружен!</b>\n\n"
            f"📂 Категория: {category_name}\n"
            f"📄 Файл: <code>{file_name}</code>\n"
            f"💾 Размер: {document.file_size / 1024:.1f} КБ",
            parse_mode="HTML",
            reply_markup=get_handbook_menu(admin)
        )
        
        await BotStates.handbook_menu.set()
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при загрузке: {e}",
            reply_markup=get_handbook_menu(admin)
        )
        await BotStates.handbook_menu.set()

# ===== СКАЧИВАНИЕ ФАЙЛОВ =====

async def file_download_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка скачивания конкретного файла"""
    
    if callback.data == "back_to_handbook":
        await callback.message.delete()
        await callback.answer()
        
        user_id = callback.from_user.id
        admin = is_admin(user_id)
        
        await callback.message.answer(
            "📚 Справочное бюро",
            reply_markup=get_handbook_menu(admin)
        )
        return
    
    # Парсим callback_data: file_category_index
    parts = callback.data.split("_", 2)
    if len(parts) < 3:
        await callback.answer("❌ Ошибка данных")
        return
    
    category = parts[1]
    file_index = int(parts[2])  # ИСПРАВЛЕНО: получаем индекс вместо имени
    
    # Получаем список файлов заново
    category_dir = os.path.join(config.DOCUMENTS_DIR, category)
    
    if not os.path.exists(category_dir):
        await callback.answer("❌ Категория не найдена", show_alert=True)
        return
    
    files = sorted([
        f for f in os.listdir(category_dir) 
        if os.path.isfile(os.path.join(category_dir, f))
    ])
    
    # Проверяем что индекс валидный
    if file_index >= len(files):
        await callback.answer("❌ Файл не найден", show_alert=True)
        return
    
    filename = files[file_index]  # ИСПРАВЛЕНО: получаем имя файла по индексу
    file_path = os.path.join(category_dir, filename)
    
    if not os.path.exists(file_path):
        await callback.answer("❌ Файл не найден", show_alert=True)
        return
    
    await callback.answer("📤 Отправляю файл...")
    
    try:
        # Отправляем файл
        with open(file_path, 'rb') as doc:
            await callback.message.answer_document(
                doc,
                caption=f"📄 {filename}"
            )
        
        await callback.answer("✅ Файл отправлен")
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков справочника"""
    
    # Меню справочника
    dp.register_message_handler(
        handbook_menu_handler, 
        state=BotStates.handbook_menu
    )
    
    # Создание категории
    dp.register_message_handler(
        create_category_handler,
        state=BotStates.handbook_creating_category
    )
    
    # Выбор категории для загрузки (inline кнопки)
    dp.register_callback_query_handler(
        category_callback_handler,
        lambda c: c.data.startswith("upload_cat_"),
        state=BotStates.handbook_uploading
    )
    
    # Загрузка файла
    dp.register_message_handler(
        document_upload_handler,
        content_types=types.ContentType.ANY,
        state=BotStates.handbook_waiting_file
    )
    
    # Скачивание конкретного файла (inline кнопки)
    dp.register_callback_query_handler(
        file_download_callback,
        lambda c: c.data.startswith("file_") or c.data == "back_to_handbook",
        state="*"
    )