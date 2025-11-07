"""
Обработчики AI-помощника для Telegram бота.
"""
import sys
import os
import logging
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Добавляем путь к AI_helper
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from AI_helper.assistant import AIAssistant
from states import BotStates
from keyboards import get_ai_menu

logger = logging.getLogger(__name__)

# Создаём один экземпляр AI Assistant
ai_assistant = None


def get_ai_assistant():
    """Ленивая инициализация AI Assistant"""
    global ai_assistant
    if ai_assistant is None:
        logger.info("🤖 Инициализация AI Assistant...")
        print("🤖 Инициализация AI Assistant...")
        ai_assistant = AIAssistant(top_k=3)
        logger.info("✅ AI Assistant готов!")
        print("✅ AI Assistant готов!")
    return ai_assistant


def get_dialog_keyboard():
    """Клавиатура для диалога с AI"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("✅ Закончить диалог"))
    keyboard.add(KeyboardButton("◀️ Главное меню"))
    return keyboard


async def ai_menu_handler(message: types.Message, state: FSMContext):
    """Обработчик меню AI"""
    logger.info(f"AI menu handler: {message.text}")
    
    text = message.text
    
    if text == "❓ Задать вопрос":
        # Очищаем историю при начале нового диалога
        await state.update_data(ai_history=[])
        
        await message.answer(
            "🤖 <b>Диалог начат!</b>\n\n"
            "Задавайте вопросы. Я помню контекст разговора.\n\n"
            "<i>Например:</i>\n"
            "• Какие документы нужны для поступления?\n"
            "• Что такое БВИ?\n"
            "• А что нужно для этого?\n\n"
            "Нажмите <b>\"✅ Закончить диалог\"</b> когда закончите.",
            parse_mode="HTML",
            reply_markup=get_dialog_keyboard()
        )
        await BotStates.ai_asking.set()
    
    elif text == "🧹 Очистить историю":
        await state.update_data(ai_history=[], ai_questions_count=0)
        await message.answer(
            "✅ История диалога очищена!",
            reply_markup=get_ai_menu()
        )
    
    elif text == "📊 Статистика":
        data = await state.get_data()
        questions_count = data.get('ai_questions_count', 0)
        history_count = len(data.get('ai_history', []))
        
        await message.answer(
            f"📊 <b>Ваша статистика:</b>\n\n"
            f"Всего вопросов: {questions_count}\n"
            f"Сообщений в текущей истории: {history_count}\n"
            f"База знаний: 645 документов\n"
            f"Модель: YandexGPT Lite",
            parse_mode="HTML",
            reply_markup=get_ai_menu()
        )
    
    else:
        await message.answer(
            "Используйте кнопки меню",
            reply_markup=get_ai_menu()
        )


async def ai_question_handler(message: types.Message, state: FSMContext):
    """Обработка вопроса к AI с контекстом"""
    
    # Проверка на кнопку "Закончить диалог"
    if message.text == "✅ Закончить диалог":
        data = await state.get_data()
        questions_count = data.get('ai_questions_count', 0)
        
        await message.answer(
            f"✅ <b>Диалог завершён!</b>\n\n"
            f"Задано вопросов: {questions_count}\n\n"
            f"Спасибо за использование AI-помощника!",
            parse_mode="HTML",
            reply_markup=get_ai_menu()
        )
        await BotStates.ai_menu.set()
        return
    
    question = message.text.strip()
    
    # Отправляем индикатор "печатает..."
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    try:
        # Получаем AI Assistant
        assistant = get_ai_assistant()
        
        # Загружаем историю диалога
        data = await state.get_data()
        history = data.get('ai_history', [])
        
        # Отправляем сообщение "Ищу информацию..."
        status_msg = await message.answer("🔍 Ищу информацию в документах...")
        
        # Формируем контекст истории
        conversation_context = ""
        if history:
            conversation_context = "ИСТОРИЯ ДИАЛОГА:\n"
            for msg in history[-6:]:  # Последние 3 пары
                role = "Пользователь" if msg['role'] == 'user' else "Ассистент"
                conversation_context += f"{role}: {msg['content']}\n"
        
        # 1. Поиск документов (чистый вопрос без истории)
        search_results = assistant.vector_store.search(question, top_k=10)
        
        # 2. Формируем контекст из документов
        context_parts = []
        for idx, result_doc in enumerate(search_results, 1):
            context_parts.append(
                f"[ДОКУМЕНТ {idx}]\n"
                f"Источник: {result_doc['file_name']}\n"
                f"Страница: {result_doc.get('page', 'N/A')}\n"
                f"Текст:\n{result_doc['text']}\n"
            )
        
        doc_context = "\n".join(context_parts)
        
        # 3. Формируем полный промпт
        full_prompt = (
            "Ты — умный помощник приёмной комиссии университета.\n\n"
            "КОНТЕКСТ ИЗ ДОКУМЕНТОВ:\n"
            f"{doc_context}\n\n"
        )
        
        if history:
            full_prompt += f"{conversation_context}\n\n"
        
        full_prompt += f"ТЕКУЩИЙ ВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{question}\n\n"
        full_prompt += (
            "ВАЖНО:\n"
            "1. Отвечай на основе предоставленного контекста\n"
            "2. Учитывай историю для понимания местоимений (\"это\", \"ней\", \"там\")\n"
            "3. Если информации нет - так и скажи\n"
            "4. Указывай источники"
        )
        
        # 4. Генерируем ответ
        from AI_helper.llm import Message
        messages = [Message(role="user", content=full_prompt)]
        answer = assistant.llm.generate(messages, temperature=0.6)
        
        # 5. Формируем результат
        result = {
            'answer': answer,
            'sources': [
                {
                    'file_name': s['file_name'],
                    'page': s.get('page'),
                    'score': s['score'],
                    'text_preview': s['text'][:200] + "..."
                }
                for s in search_results
            ]
        }
        
        # Удаляем статус
        await status_msg.delete()
        
        # Форматируем ответ
        answer_text = f"💬 <b>Ответ:</b>\n\n{result['answer']}"
        
        # Добавляем источники
        if result['sources']:
            answer_text += "\n\n📚 <b>Источники:</b>\n"
            for i, source in enumerate(result['sources'][:3], 1):
                page_info = f", стр. {source['page']}" if source['page'] else ""
                answer_text += f"{i}. {source['file_name']}{page_info}\n"
        
        # Отправляем ответ
        if len(answer_text) > 4000:
            parts = [answer_text[i:i+4000] for i in range(0, len(answer_text), 4000)]
            for part in parts:
                await message.answer(part, parse_mode="HTML", reply_markup=get_dialog_keyboard())
        else:
            await message.answer(answer_text, parse_mode="HTML", reply_markup=get_dialog_keyboard())
        
        # Сохраняем в историю
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": result['answer']})
        
        # Ограничиваем историю
        if len(history) > 10:
            history = history[-10:]
        
        # Обновляем FSM
        questions_count = data.get('ai_questions_count', 0)
        await state.update_data(
            ai_history=history,
            ai_questions_count=questions_count + 1
        )
        
    except Exception as e:
        logger.error(f"Ошибка AI: {e}", exc_info=True)
        await message.answer(
            f"❌ Произошла ошибка:\n<code>{str(e)}</code>",
            parse_mode="HTML",
            reply_markup=get_dialog_keyboard()
        )


async def cancel_ai_question(message: types.Message, state: FSMContext):
    """Отмена вопроса к AI"""
    await message.answer("❌ Диалог отменён", reply_markup=get_ai_menu())
    await BotStates.ai_menu.set()


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков AI"""
    dp.register_message_handler(ai_menu_handler, state=BotStates.ai_menu)
    dp.register_message_handler(ai_question_handler, state=BotStates.ai_asking)
    dp.register_message_handler(cancel_ai_question, commands=['cancel'], state=BotStates.ai_asking)