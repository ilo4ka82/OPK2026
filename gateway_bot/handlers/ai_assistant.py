"""
Обработчики AI-помощника для Telegram бота.
"""
import sys
import os
import time
import logging
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Добавляем путь к AI_helper
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from AI_helper.assistant import AIAssistant
from AI_helper.query_processor import QueryProcessor
from AI_helper.logger import AILogger
from states import BotStates
from keyboards import get_ai_menu

logger = logging.getLogger(__name__)

# Создаём один экземпляр AI Assistant
ai_assistant = None

query_processor = QueryProcessor()

# Создаём экземпляр логгера
ai_logger = AILogger()


def get_ai_assistant():
    """Ленивая инициализация AI Assistant"""
    global ai_assistant
    if ai_assistant is None:
        logger.info("🤖 Инициализация AI Assistant...")
        print("🤖 Инициализация AI Assistant...")
        ai_assistant = AIAssistant(top_k=10)
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
    start_time = time.time()
    
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
        
        # 1. Предобработка запроса
        processed_query = query_processor.process(question)
        logger.info(f"🔄 Обработанный запрос: {processed_query}")

        # 2. Поиск документов
        search_results = assistant.vector_store.search(processed_query, top_k=10)

        # 3. Фильтрация по релевантности
        max_relevance = max([s['score'] for s in search_results]) if search_results else 0
        logger.info(f"🎯 Максимальная релевантность: {max_relevance:.3f}")

        if max_relevance < 0.6:
            # Релевантность слишком низкая - информации нет
            await status_msg.delete()
            
            no_info_text = (
                "🤔 <b>К сожалению, я не нашёл информацию по вашему вопросу в документах.</b>\n\n"
                "Рекомендую:\n"
                "• Переформулировать вопрос\n"
                "• Обратиться в приёмную комиссию:\n"
                "  📞 Телефон: +7 (495) 957-72-32\n"
                "  📧 Email: priem@mtuci.ru\n"
                "  🌐 Сайт: mtuci.ru\n\n"
                "<i>Попробуйте задать более конкретный вопрос или использовать другие формулировки.</i>"
            )
            
            await message.answer(no_info_text, parse_mode="HTML", reply_markup=get_dialog_keyboard())
            
            # Логируем низкую релевантность
            response_time_ms = int((time.time() - start_time) * 1000)
            
            request_id = ai_logger.log_request(
                user_id=message.from_user.id,
                username=message.from_user.username or message.from_user.first_name,
                question=question,
                answer="[Информация не найдена - низкая релевантность]",
                sources=search_results,
                response_time_ms=response_time_ms,
                context_length=0
            )
            
            logger.warning(f"⚠️ Низкая релевантность ({max_relevance:.3f}) для запроса: {question}")
            
            # Обновляем FSM
            questions_count = data.get('ai_questions_count', 0)
            await state.update_data(
                ai_history=history,
                ai_questions_count=questions_count + 1
            )
            
            return  # ✅ ВАЖНО! Выходим из функции
        
        # 4. Формируем контекст из документов
        context_parts = []
        for idx, result_doc in enumerate(search_results, 1):
            context_parts.append(
                f"[ДОКУМЕНТ {idx}]\n"
                f"Источник: {result_doc['file_name']}\n"
                f"Страница: {result_doc.get('page', 'N/A')}\n"
                f"Текст:\n{result_doc['text']}\n"
            )
        
        doc_context = "\n".join(context_parts)
        
        # 5. Формируем полный промпт
        from AI_helper.prompts import build_full_prompt
        
        full_prompt = build_full_prompt(
            question=question,
            doc_context=doc_context,
            conversation_history=conversation_context if history else None
        )
        
        # 6. Генерируем ответ
        from AI_helper.llm import Message
        messages = [Message(role="user", content=full_prompt)]
        answer = assistant.llm.generate(messages, temperature=0.6)
        
        # 7. Формируем результат
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
        
        # ✅ ЛОГИРОВАНИЕ
        response_time_ms = int((time.time() - start_time) * 1000)
        
        request_id = ai_logger.log_request(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            question=question,
            answer=result['answer'],
            sources=result['sources'],
            response_time_ms=response_time_ms,
            context_length=len(doc_context)
        )
        
        logger.info(f"✅ Запрос #{request_id} залогирован")
        
        # ✅ КНОПКИ ОЦЕНКИ
        feedback_keyboard = InlineKeyboardMarkup(row_width=2)
        feedback_keyboard.add(
            InlineKeyboardButton("👍 Полезно", callback_data=f"fb_pos_{request_id}"),
            InlineKeyboardButton("👎 Не помогло", callback_data=f"fb_neg_{request_id}")
        )
        
        await message.answer(
            "Был ли ответ полезен?",
            reply_markup=feedback_keyboard
        )
        
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


async def feedback_handler(callback_query: types.CallbackQuery):
    """Обработка обратной связи"""
    data = callback_query.data
    
    logger.info(f"🔔 Получен callback: {data}")  # ✅ ДОБАВЛЕНО
    print(f"🔔 Получен callback: {data}")  # ✅ ДОБАВЛЕНО
    
    try:
        if data.startswith("fb_pos_"):
            request_id = int(data.replace("fb_pos_", ""))
            logger.info(f"👍 Положительная оценка для запроса #{request_id}")  # ✅ ДОБАВЛЕНО
            ai_logger.log_feedback(request_id, feedback=1)
            await callback_query.answer("✅ Спасибо за оценку!")
            
        elif data.startswith("fb_neg_"):
            request_id = int(data.replace("fb_neg_", ""))
            logger.info(f"👎 Отрицательная оценка для запроса #{request_id}")  # ✅ ДОБАВЛЕНО
            ai_logger.log_feedback(request_id, feedback=-1)
            await callback_query.answer("Спасибо! Мы учтём ваш отзыв.")
        
        # Удаляем кнопки после оценки
        await callback_query.message.edit_reply_markup(reply_markup=None)
        logger.info("✅ Кнопки удалены")  # ✅ ДОБАВЛЕНО
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки feedback: {e}", exc_info=True)  # ✅ ДОБАВЛЕНО
        await callback_query.answer("Ошибка сохранения оценки")

async def cancel_ai_question(message: types.Message, state: FSMContext):
    """Отмена вопроса к AI"""
    await message.answer("❌ Диалог отменён", reply_markup=get_ai_menu())
    await BotStates.ai_menu.set()


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков AI"""
    dp.register_message_handler(ai_menu_handler, state=BotStates.ai_menu)
    dp.register_message_handler(ai_question_handler, state=BotStates.ai_asking)
    dp.register_message_handler(cancel_ai_question, commands=['cancel'], state=BotStates.ai_asking)
    
    dp.register_callback_query_handler(
        feedback_handler, 
        lambda c: c.data and c.data.startswith("fb_"),
        state="*"  # ДОБАВЛЕНО - работает в любом state
    )
    
    print("✅ AI handlers registered (including feedback)")