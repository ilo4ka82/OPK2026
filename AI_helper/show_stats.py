"""
Простой скрипт для просмотра статистики
"""
from logger import AILogger


def main():
    logger = AILogger()
    
    print("\n" + "="*60)
    print("📊 AI ПОМОЩНИК - СТАТИСТИКА")
    print("="*60)
    
    # Статистика за неделю
    stats = logger.get_stats(days=7)
    print(f"\n📈 За последние 7 дней:")
    print(f"  Всего запросов: {stats['total_requests']}")
    print(f"  Среднее время ответа: {stats['avg_response_time_ms']} мс")
    print(f"  Средняя релевантность: {stats['avg_relevance']}")
    print(f"  👍 Положительных оценок: {stats['positive_feedback']}")
    print(f"  👎 Отрицательных оценок: {stats['negative_feedback']}")
    print(f"  Процент оценок: {stats['feedback_rate']}%")
    
    # Популярные вопросы
    print(f"\n🔥 Топ-10 вопросов:")
    popular = logger.get_popular_questions(limit=10)
    for i, q in enumerate(popular, 1):
        print(f"  {i}. ({q['count']}x) {q['question'][:60]}...")
    
    # Проблемные запросы
    print(f"\n⚠️ Запросы с низкой релевантностью (<0.6):")
    low_relevance = logger.get_low_relevance_requests(threshold=0.6, limit=10)
    for i, req in enumerate(low_relevance, 1):
        print(f"  {i}. [{req['relevance']:.2f}] {req['question'][:60]}...")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()