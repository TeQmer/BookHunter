"""
Утилиты для умного поиска книг

Содержит функции для:
- Проверки совпадения книги с поисковым запросом (70% слов)
- Определения нагрузки сервера
- Управления очередью допарсинга через Redis
"""

import re
import hashlib
import os
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import redis.asyncio as redis
from services.logger import logger

# Константы
MIN_WORDS_FOR_MATCH = 2  # Минимум слов в запросе для fuzzy match
MATCH_THRESHOLD = 0.7    # 70% совпадение слов
SHORT_WORDS = {'и', 'в', 'на', 'с', 'от', 'до', 'по', 'о', 'об', 'а', 'но', 'ли', 'же', 'бы', 'их', 'её', 'его', 'это', 'то', 'как', 'за', 'при', 'для', 'из', 'к', 'со', 'под', 'над', 'между', 'под', 'без', 'ко', 'со'}
PARSE_LIMIT_NORMAL = 25   # Лимит при нормальной нагрузке
PARSE_LIMIT_LOADED = 10   # Лимит при высокой нагрузке
ONLINE_USERS_THRESHOLD = 50  # Порог онлайн пользователей для определения нагрузки
PENDING_PARSE_TTL = 86400  # 24 часа в секундах


def normalize_text(text: str) -> str:
    """
    Нормализует текст для сравнения:
    - Нижний регистр
    - Удаление знаков препинания
    - Удаление лишних пробелов
    """
    if not text:
        return ""
    
    # Нижний регистр
    text = text.lower().strip()
    
    # Удаляем знаки препинания и специальные символы
    text = re.sub(r'[,\.\!\?\:\;\-\—\(\)\[\]\{\}<>«»\'\"\\/]+', ' ', text)
    
    # Удаляем лишние пробелы
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def get_words_set(text: str) -> set:
    """
    Извлекает значимые слова из текста (без предлогов и коротких слов)
    """
    normalized = normalize_text(text)
    words = normalized.split()
    
    # Удаляем короткие слова (предлоги, союзы и т.д.)
    significant_words = {w for w in words if len(w) > 2 and w not in SHORT_WORDS}
    
    return significant_words


def calculate_match_percentage(query_words: set, title_words: set) -> float:
    """
    Вычисляет процент совпадения слов запроса со словами в названии
    
    Returns:
        Процент совпадения от 0 до 1
    """
    if not query_words:
        return 0.0
    
    matches = len(query_words & title_words)
    return matches / len(query_words)


def is_book_similar(query: str, book_title: str, book_author: str = None) -> Tuple[bool, str]:
    """
    Проверяет, похож ли запрос на книгу в базе
    
    Логика:
    1. Точное совпадение названия -> считаем совпадением
    2. Одно слово в запросе -> только если автор точно совпадает
    3. 2+ слова в запросе -> 70% совпадение слов ИЛИ автор + 30% совпадение
    
    Args:
        query: Поисковый запрос пользователя
        book_title: Название книги в базе
        book_author: Автор книги в базе (опционально)
    
    Returns:
        Кортеж (is_similar: bool, reason: str)
    """
    query_normalized = normalize_text(query)
    title_normalized = normalize_text(book_title)
    author_normalized = normalize_text(book_author) if book_author else ""
    
    query_words = get_words_set(query)
    title_words = get_words_set(book_title)
    
    # 1. Точное совпадение названия
    if query_normalized == title_normalized:
        return True, "exact_title_match"
    
    # 2. Одно слово в запросе - слишком слабо, требуем автора
    if len(query_words) <= 1:
        if author_normalized and author_normalized in query_normalized:
            return True, "single_word_with_author"
        return False, "single_word_no_author_match"
    
    # 3. Вычисляем процент совпадения слов
    match_percentage = calculate_match_percentage(query_words, title_words)
    
    # 4. Проверяем по автору
    author_match = False
    if author_normalized:
        # Автор содержится в запросе (полностью или частично)
        author_match = (
            author_normalized in query_normalized or 
            query_normalized in author_normalized or
            any(author_word in query_words for author_word in get_words_set(book_author))
        )
    
    # 5. Применяем логику совпадения
    if author_match and match_percentage >= 0.3:
        # Автор совпадает + минимум 30% слов названия
        return True, f"author_match_{int(match_percentage*100)}%"
    
    if match_percentage >= MATCH_THRESHOLD:
        # Минимум 70% слов совпадает
        return True, f"words_match_{int(match_percentage*100)}%"
    
    return False, f"no_match_{int(match_percentage*100)}%"


def is_exact_match(query: str, book_title: str) -> bool:
    """
    Проверяет точное совпадение запроса и названия книги
    """
    query_norm = normalize_text(query)
    title_norm = normalize_text(book_title)
    
    return query_norm == title_norm or query_norm in title_norm or title_norm in query_norm


# ========== НАГРУЗКА СЕРВЕРА ==========

def get_current_online_users() -> int:
    """
    Получает количество онлайн пользователей
    
    TODO: Реализовать через WebSocket connections или Redis
    Пока возвращает заглушку
    """
    # В будущем можно использовать:
    # - Redis: INCR/DECR при подключении/отключении WebSocket
    # - Метрики из Telegram Mini App
    # - Количество активных сессий
    
    # Пока возвращаем 0 (нормальная нагрузка)
    return 0


def should_limit_parsing() -> Tuple[bool, int]:
    """
    Определяет, нужно ли ограничивать парсинг
    
    Returns:
        Кортеж (should_limit: bool, limit: int)
    """
    online_users = get_current_online_users()
    
    if online_users > ONLINE_USERS_THRESHOLD:
        logger.info(f"Высокая нагрузка: {online_users} пользователей онлайн. Лимит парсинга: {PARSE_LIMIT_LOADED}")
        return True, PARSE_LIMIT_LOADED
    else:
        logger.info(f"Нормальная нагрузка: {online_users} пользователей онлайн. Лимит парсинга: {PARSE_LIMIT_NORMAL}")
        return False, PARSE_LIMIT_NORMAL


# ========== REDIS ОЧЕРЕДЬ ДОПАРСИНГА ==========

async def get_redis_client():
    """Получает асинхронный Redis клиент"""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    # Убираем пароль из URL для подключения
    redis_url = redis_url.replace(":@", "://")
    
    # Парсим URL и добавляем пароль
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(redis_url)
        if os.getenv("REDIS_PASSWORD"):
            redis_url = f"redis://:{os.getenv('REDIS_PASSWORD')}@{parsed.hostname}:{parsed.port or 6379}{parsed.path}"
    except:
        pass
    
    return redis.from_url(redis_url, decode_responses=True)


def generate_pending_key(query: str) -> str:
    """Генерирует ключ для Redis очереди допарсинга"""
    query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
    return f"pending_parse:{query_hash}"


async def add_to_pending_parse(query: str, author: str = None, already_parsed_count: int = 0):
    """
    Добавляет запрос в очередь допарсинга
    
    Args:
        query: Поисковый запрос
        author: Автор (если известен)
        already_parsed_count: Количество уже спарсенных книг
    """
    try:
        redis_client = await get_redis_client()
        key = generate_pending_key(query)
        
        data = {
            "query": query,
            "author": author or "",
            "already_parsed": already_parsed_count,
            "created_at": datetime.now().isoformat()
        }
        
        # Сохраняем с TTL 24 часа
        await redis_client.hset(key, mapping=data)
        await redis_client.expire(key, PENDING_PARSE_TTL)
        
        logger.info(f"Добавлено в очередь допарсинга: {query} (уже парсено: {already_parsed_count})")
        
        await redis_client.close()
    except Exception as e:
        logger.error(f"Ошибка добавления в очередь допарсинга: {e}")


async def get_pending_parse(query: str) -> Optional[dict]:
    """
    Получает информацию о допарсинге для запроса
    
    Returns:
        Словарь с данными или None если не найдено
    """
    try:
        redis_client = await get_redis_client()
        key = generate_pending_key(query)
        
        data = await redis_client.hgetall(key)
        await redis_client.close()
        
        if data:
            return {
                "query": data.get("query"),
                "author": data.get("author"),
                "already_parsed": int(data.get("already_parsed", 0)),
                "created_at": data.get("created_at")
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка получения из очереди допарсинга: {e}")
        return None


async def remove_from_pending_parse(query: str):
    """
    Удаляет запрос из очереди допарсинга (после завершения)
    """
    try:
        redis_client = await get_redis_client()
        key = generate_pending_key(query)
        
        await redis_client.delete(key)
        
        logger.info(f"Удалено из очереди допарсинга: {query}")
        
        await redis_client.close()
    except Exception as e:
        logger.error(f"Ошибка удаления из очереди допарсинга: {e}")


async def check_and_complete_pending_parse(query: str) -> Tuple[bool, int]:
    """
    Проверяет и завершает допарсинг для запроса
    
    Returns:
        Кортеж (needs_more_parsing: bool, additional_limit: int)
    """
    pending = await get_pending_parse(query)
    
    if pending:
        # Запрос есть в очереди - нужно допарсить
        already_parsed = pending.get("already_parsed", 0)
        additional_limit = max(0, PARSE_LIMIT_NORMAL - already_parsed)
        
        logger.info(f"Допарсинг для {query}: уже парсено {already_parsed}, нужно еще {additional_limit}")
        
        # Удаляем из очереди после обработки
        await remove_from_pending_parse(query)
        
        return True, additional_limit
    
    return False, 0


# ========== ПРИМЕРЫ РАБОТЫ ==========

if __name__ == "__main__":
    # Тесты
    test_cases = [
        ("Вторая жизнь", "Тамплиеры: жизнь после смерти", "Дмитрий Жуков"),
        ("Вторая жизнь", "Вторая жизнь. Книга 1", "Иван Иванов"),
        ("Python для чайников", "Python для чайников", "Иван Петров"),
        ("Стив Джобс", "Биография Стива Джобса", "Уолтер Айзексон"),
        ("Война и мир", "Война и мир", "Лев Толстой"),
    ]
    
    print("=" * 60)
    print("ТЕСТЫ УМНОГО ПОИСКА")
    print("=" * 60)
    
    for query, title, author in test_cases:
        is_similar, reason = is_book_similar(query, title, author)
        status = "✅ НАЙДЕНО" if is_similar else "❌ НЕ НАЙДЕНО"
        print(f"\nЗапрос: '{query}'")
        print(f"Книга: '{title}' - {author}")
        print(f"Результат: {status} ({reason})")
