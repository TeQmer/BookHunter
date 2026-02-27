from typing import List, Dict, Optional, Tuple
from celery import current_app
from services.logger import celery_logger
from database.config import get_session_factory, AsyncSession
from models import Alert, Book as DBBook, Notification, User, ParsingLog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from datetime import datetime, timedelta
import asyncio
import traceback
import json
import os
import sys
import time

# Импортируем класс Book для парсеров
from parsers.base import Book as ParserBook

# Импортируем celery_app после создания, чтобы избежать циклического импорта
from services.celery_app import celery_app

# Импортируем утилиты умного поиска
from services.search_utils import (
    is_book_similar, 
    is_exact_match, 
    should_limit_parsing,
    add_to_pending_parse,
    check_and_complete_pending_parse,
    PARSE_LIMIT_NORMAL,
    PARSE_LIMIT_LOADED
)

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3})
def check_all_alerts(self):
    """Проверка всех активных подписок пользователей с реальным парсером"""
    
    def run_async_task():
        """Запуск асинхронной задачи в синхронном контексте Celery"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_check_all_alerts_async())
        finally:
            loop.close()
    
    try:
        result = run_async_task()
        celery_logger.info(f"Проверка подписок завершена. Найдено книг: {result}")
        return result
    except Exception as e:
        celery_logger.error(f"Ошибка при проверке подписок: {e}")
        celery_logger.error(traceback.format_exc())
        raise

# Регистрируем задачу
check_all_alerts_task = celery_app.task(check_all_alerts, bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3})

async def _check_all_alerts_async():
    """Асинхронная функция проверки подписок с реальным парсингом"""
    
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # Получаем все активные подписки
            result = await db.execute(
                select(Alert).where(Alert.is_active == True)
            )
            alerts = result.scalars().all()
            
            if not alerts:
                celery_logger.info("Нет активных подписок для проверки")
                return 0
            
            # Импортируем реальный парсер
            try:
                import sys
                import os
                # Добавляем корневую папку в PYTHONPATH
                current_dir = os.path.dirname(os.path.abspath(__file__))
                root_dir = os.path.dirname(os.path.dirname(current_dir))
                if root_dir not in sys.path:
                    sys.path.append(root_dir)
                
                from parsers.chitai_gorod import ChitaiGorodParser
                parser = ChitaiGorodParser()
            except ImportError as e:
                celery_logger.warning(f"Не удалось импортировать парсер: {e}")
                # Создаем заглушку для демонстрации
                parser = MockParser()
            
            books_found = 0
            notifications_created = 0
            
            for alert in alerts:
                try:
                    # Формируем запрос для поиска
                    search_query = alert.book_title
                    if alert.book_author:
                        search_query += f" {alert.book_author}"
                    
                    celery_logger.info(f"Поиск книг для подписки {alert.id}: '{search_query}'")
                    
                    # Реальный поиск книг
                    books = await parser.search_books(search_query)
                    
                    if not books:
                        celery_logger.info(f"Книги не найдены для запроса: {search_query}")
                        continue
                    
                    # Фильтруем книги по условиям подписки
                    suitable_books = []
                    for book in books:
                        if await _is_book_suitable_for_alert(book, alert):
                            suitable_books.append(book)
                    
                    if suitable_books:
                        # Берем лучшую книгу (с максимальной скидкой)
                        best_book = max(suitable_books, key=lambda x: x.discount_percent or 0)
                        
                        # Проверяем, не отправляли ли мы уже уведомление для этой книги
                        if not await _was_notification_sent_recently(db, alert.id, best_book.source_id):
                            
                            # Сохраняем книгу в БД
                            await _save_book(db, best_book)
                            
                            # Добавляем в Google Sheets
                            await _add_to_sheets(best_book)
                            
                            # Создаем уведомление
                            notification = await _create_notification(db, alert, best_book)
                            if notification:
                                notifications_created += 1
                                
                                # Отправляем уведомление через Telegram
                                await _send_telegram_notification(alert.user_id, best_book, alert)
                            
                            books_found += 1
                            celery_logger.info(f"Найдена подходящая книга: {best_book.title} - {best_book.current_price}₽ (скидка {best_book.discount_percent}%)")
                        
                    else:
                        celery_logger.info(f"Нет подходящих книг для подписки {alert.id}")
                    
                    # Задержка между запросами для вежливого парсинга
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    celery_logger.error(f"Ошибка обработки подписки {alert.id}: {e}")
                    continue
                
            # Логируем результат
            await _log_parsing_result(db, "alert_check", "success", 
                                    f"Проверено {len(alerts)} подписок, найдено {books_found} книг, создано {notifications_created} уведомлений")
            
            return books_found
            
        except Exception as e:
            celery_logger.error(f"Критическая ошибка при проверке подписок: {e}")
            await _log_parsing_result(db, "alert_check", "error", str(e))
            raise

async def _is_book_suitable_for_alert(book: ParserBook, alert: Alert) -> bool:
    """Проверка, подходит ли книга под условия подписки"""
    
    # Проверка максимальной цены
    if alert.max_price and book.current_price > alert.max_price:
        return False
    
    # Проверка минимальной скидки
    if alert.min_discount and (book.discount_percent or 0) < alert.min_discount:
        return False
    
    # Проверка соответствия запросу (простая проверка по названию)
    if alert.book_title:
        query_words = alert.book_title.lower().split()
        book_title = book.title.lower()
        if not any(word in book_title for word in query_words):
            return False
    
    return True

async def _was_notification_sent_recently(db, alert_id: int, book_source_id: str) -> bool:
    """Проверка, не отправляли ли мы уведомление недавно для этой книги"""
    
    # Проверяем уведомления за последние 24 часа
    cutoff_time = datetime.now() - timedelta(hours=24)
    
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.alert_id == alert_id,
                Notification.created_at > cutoff_time
            )
        )
    )
    recent_notifications = result.scalars().all()
    
    # Проверяем, есть ли уведомление для этой книги
    for notification in recent_notifications:
        # Здесь можно добавить логику сравнения с source_id книги
        # Пока просто проверяем по URL или другим признакам
        if notification.url and "product" in notification.url and book_source_id in notification.url:
            return True
    
    return False

async def _save_book(db: AsyncSession, book: ParserBook):
    """Сохранение книги в базу данных"""
    
    try:
        # Проверяем, существует ли книга
        result = await db.execute(
            select(DBBook).where(
                and_(DBBook.source == book.source, DBBook.source_id == book.source_id)
            )
        )
        existing_book = result.scalar_one_or_none()
        
        if existing_book:
            # Обновляем существующую книгу
            existing_book.current_price = book.current_price
            existing_book.original_price = book.original_price
            existing_book.discount_percent = book.discount_percent
            existing_book.parsed_at = book.parsed_at
            
            # Обновляем дополнительные поля если они изменились
            if book.title != existing_book.title:
                existing_book.title = book.title
            if book.author != existing_book.author:
                existing_book.author = book.author
            if book.publisher != existing_book.publisher:
                existing_book.publisher = book.publisher
            if book.binding != existing_book.binding:
                existing_book.binding = book.binding
            if book.image_url != existing_book.image_url:
                existing_book.image_url = book.image_url
                
            # Обновляем жанры если они есть
            if book.genres:
                genres_json = json.dumps(book.genres)
                existing_book.genres = genres_json

            # Обновляем ISBN если он есть
            if book.isbn:
                existing_book.isbn = book.isbn
                
        else:
            # Создаем новую книгу
            # Преобразуем genres в JSON строку для сохранения в БД
            genres_json = json.dumps(book.genres) if book.genres else None
            
            db_book = DBBook(
                source=book.source,
                source_id=book.source_id,
                title=book.title,
                author=book.author,
                publisher=book.publisher,
                binding=book.binding,
                current_price=book.current_price,
                original_price=book.original_price,
                discount_percent=book.discount_percent,
                url=book.url,
                image_url=book.image_url,
                genres=genres_json,
                isbn=book.isbn,
                parsed_at=book.parsed_at
            )
            db.add(db_book)
        
        await db.commit()
        
    except Exception as e:
        celery_logger.error(f"Ошибка сохранения книги: {e}")
        await db.rollback()

async def _add_to_sheets(book: ParserBook):
    """Добавление книги в Google Sheets (устарело - используй _add_to_sheets_batch)"""
    # Для обратной совместимости
    await _add_to_sheets_batch([book])


async def _add_to_sheets_batch(books: List[ParserBook], max_books: int = 5):
    """
    Добавление книг в Google Sheets (только топ-N самых дешёвых)

    Args:
        books: Список найденных книг
        max_books: Максимальное количество книг для добавления (по умолчанию 5)
    """
    try:
        from services.sheets_manager import SheetManager
        sheets_manager = SheetManager()
        # Передаём весь список - метод сам выберет топ-5 дешёвых
        await sheets_manager.add_books_batch(books, max_books=max_books)
    except Exception as e:
        celery_logger.error(f"Ошибка добавления в Google Sheets: {e}")
        # Не прерываем выполнение из-за ошибки с Sheets

async def _create_notification(db: AsyncSession, alert: Alert, book: ParserBook):
    """Создание уведомления о найденной книге"""
    
    try:
        # Получаем пользователя
        result = await db.execute(select(User).where(User.id == alert.user_id))
        user = result.scalar_one()
        
        notification = Notification(
            user_id=user.id,
            book_id=None,  # Будет заполнено после сохранения книги
            alert_id=alert.id,
            title=book.title,
            author=book.author,
            current_price=book.current_price,
            original_price=book.original_price,
            discount_percent=book.discount_percent,
            url=book.url,
            image_url=book.image_url
        )

        db.add(notification)
        await db.commit()
        
        return notification
        
    except Exception as e:
        celery_logger.error(f"Ошибка создания уведомления: {e}")
        await db.rollback()
        return None

async def _send_telegram_notification(user_id: int, book: ParserBook, alert: Alert):
    """Отправка уведомления через Telegram Bot"""
    
    try:
        from app.bot.telegram_bot import TelegramBot
        bot = TelegramBot()
        
        # Формируем сообщение
        message = f"📚 <b>Найдена книга по вашей подписке!</b>\n\n"
        message += f"📖 <b>{book.title}</b>\n"
        if book.author:
            message += f"👤 Автор: {book.author}\n"
        message += f"💰 Цена: <b>{book.current_price} руб.</b>\n"
        if book.original_price and book.original_price > book.current_price:
            message += f"💸 Старая цена: <s>{book.original_price} руб.</s>\n"
        if book.discount_percent:
            message += f"🔥 Скидка: <b>{book.discount_percent}%</b>\n"
        message += f"\n🔗 <a href='{book.url}'>Ссылка на книгу</a>"
        
        if alert.max_price:
            message += f"\n\n✅ Цена соответствует вашему лимиту ({alert.max_price} руб.)"
        
        # Отправляем сообщение
        await bot.send_message(user_id, message)
        
        celery_logger.info(f"Уведомление отправлено пользователю {user_id} для книги {book.title}")
        
    except Exception as e:
        celery_logger.error(f"Ошибка отправки Telegram уведомления: {e}")

async def _log_parsing_result(db: AsyncSession, source: str, status: str, message: str):
    """Логирование результата парсинга"""
    
    try:
        # Временно отключаем логирование для диагностики
        # Можно добавить логирование позже
        celery_logger.info(f"Логирование (отключено): {source} - {status} - {message}")
        # db.add(log_entry)
        # await db.commit()
        
    except Exception as e:
        celery_logger.error(f"Ошибка логирования: {e}")
        # Не прерываем выполнение из-за ошибки логирования

@celery_app.task
def cleanup_old_logs():
    """Очистка старых логов парсинга"""
    
    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_cleanup_old_logs_async())
        finally:
            loop.close()
    
    try:
        result = run_async_task()
        celery_logger.info(f"Очистка логов завершена. Удалено записей: {result}")
        return result
    except Exception as e:
        celery_logger.error(f"Ошибка при очистке логов: {e}")
        raise

async def _cleanup_old_logs_async():
    """Асинхронная очистка старых логов"""
    
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # Удаляем логи старше 30 дней
            cutoff_date = datetime.now() - timedelta(days=30)
            
            result = await db.execute(
                select(ParsingLog).where(ParsingLog.created_at < cutoff_date)
            )
            old_logs = result.scalars().all()
            
            for log in old_logs:
                await db.delete(log)
            
            await db.commit()
            
            celery_logger.info(f"Удалено {len(old_logs)} старых логов")
            return len(old_logs)
            
        except Exception as e:
            celery_logger.error(f"Ошибка очистки логов: {e}")
            await db.rollback()
            return 0

@celery_app.task
def test_task():
    """Тестовая задача для проверки работы Celery"""
    celery_logger.info("Тестовая задача выполнена успешно!")
    return "Test completed"

@celery_app.task
def test_simple(query: str):
    """Простая тестовая задача без сложных импортов"""
    from datetime import datetime
    
    celery_logger.info(f"DEBUG: test_simple started with query: {query}")
    
    try:
        # Простая обработка без файловых операций
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Простая логика обработки
        result = {
            "status": "success",
            "message": f"Simple test completed for query: {query}",
            "query": query,
            "timestamp": timestamp,
            "processed_at": datetime.now().isoformat()
        }
        
        celery_logger.info(f"DEBUG: test_simple completed successfully: {result}")
        return result
        
    except Exception as e:
        celery_logger.error(f"DEBUG: Error in test_simple: {e}")
        celery_logger.error(traceback.format_exc())
        return {"error": str(e)}

class MockParser:
    """Заглушка парсера для демонстрации функциональности"""
    
    async def search_books(self, query: str, max_pages: int = 1, limit: int = None) -> List[ParserBook]:
        """Мок-парсер, возвращающий демо-книги до 550 рублей"""
        
        # Создаем демо-книги для демонстрации (цены до 550 рублей)
        demo_books = [
            ParserBook(
                source="chitai-gorod",
                source_id=f"demo-{query}-1",
                title=f"Изучаем {query}: базовый курс",
                author="Иван Петров",
                current_price=299.0,
                original_price=499.0,
                discount_percent=40,
                url=f"https://chitai-gorod.ru/search?phrase={query}",
                image_url="https://cdn.chitai-gorod.ru/images/covers/demo.jpg",
                parsed_at=datetime.now()
            ),
            ParserBook(
                source="chitai-gorod",
                source_id=f"demo-{query}-2",
                title=f"{query} для начинающих: пошаговое руководство",
                author="Мария Сидорова",
                current_price=349.0,
                original_price=599.0,
                discount_percent=42,
                url=f"https://chitai-gorod.ru/search?phrase={query}&page=2",
                image_url="https://cdn.chitai-gorod.ru/images/covers/demo2.jpg",
                parsed_at=datetime.now()
            ),
            ParserBook(
                source="chitai-gorod",
                source_id=f"demo-{query}-3",
                title=f"Практический {query}: упражнения и примеры",
                author="Алексей Козлов",
                current_price=399.0,
                original_price=699.0,
                discount_percent=43,
                url=f"https://chitai-gorod.ru/search?phrase={query}&page=3",
                image_url="https://cdn.chitai-gorod.ru/images/covers/demo3.jpg",
                parsed_at=datetime.now()
            ),
            ParserBook(
                source="chitai-gorod",
                source_id=f"demo-{query}-4",
                title=f"{query}: от основ до мастерства",
                author="Елена Новикова",
                current_price=449.0,
                original_price=799.0,
                discount_percent=44,
                url=f"https://chitai-gorod.ru/search?phrase={query}&page=4",
                image_url="https://cdn.chitai-gorod.ru/images/covers/demo4.jpg",
                parsed_at=datetime.now()
            ),
            ParserBook(
                source="chitai-gorod",
                source_id=f"demo-{query}-5",
                title=f"Экспертный {query}: продвинутые техники",
                author="Дмитрий Смирнов",
                current_price=499.0,
                original_price=899.0,
                discount_percent=45,
                url=f"https://chitai-gorod.ru/search?phrase={query}&page=5",
                image_url="https://cdn.chitai-gorod.ru/images/covers/demo5.jpg",
                parsed_at=datetime.now()
            ),
            ParserBook(
                source="chitai-gorod",
                source_id=f"demo-{query}-6",
                title=f"{query} в действии: реальные проекты",
                author="Анна Волкова",
                current_price=529.0,
                original_price=999.0,
                discount_percent=47,
                url=f"https://chitai-gorod.ru/search?phrase={query}&page=6",
                image_url="https://cdn.chitai-gorod.ru/images/covers/demo6.jpg",
                parsed_at=datetime.now()
            ),
            ParserBook(
                source="chitai-gorod",
                source_id=f"demo-{query}-7",
                title=f"Полный курс {query}: теория и практика",
                author="Сергей Орлов",
                current_price=549.0,
                original_price=1099.0,
                discount_percent=50,
                url=f"https://chitai-gorod.ru/search?phrase={query}&page=7",
                image_url="https://cdn.chitai-gorod.ru/images/covers/demo7.jpg",
                parsed_at=datetime.now()
            )
        ]
        
        # Применяем лимит, если указан
        if limit is not None:
            demo_books = demo_books[:limit]
        
        celery_logger.info(f"MockParser: создано {len(demo_books)} демо-книг для запроса '{query}' (цены до 550 руб., max_pages={max_pages}, limit={limit})")
        return demo_books
    
    async def check_discounts(self) -> List[ParserBook]:
        """Мок-метод для проверки скидок"""
        return []

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3})
def parse_books(self, query: str, source: str = "chitai-gorod", fetch_details: bool = False):
    """Задача для парсинга книг по запросу с реальным парсером

    Args:
        query: Поисковый запрос
        source: Источник парсинга (по умолчанию chitai-gorod)
        fetch_details: Загружать ли детальную страницу для извлечения характеристик (издательство, переплёт, жанры)
    """

    def run_async_task():
        # Проверяем, есть ли уже запущенный event loop
        try:
            loop = asyncio.get_running_loop()
            celery_logger.warning("Event loop уже запущен, создаем новый")
            # Если loop уже запущен, создаем новый в отдельном потоке
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _parse_books_async(query, source, fetch_details))
                return future.result()
        except RuntimeError:
            # Нет запущенного loop, можно создать новый
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_parse_books_async(query, source, fetch_details))
            finally:
                loop.close()
    
    try:
        # ДИАГНОСТИКА: Логируем начало задачи
        celery_logger.info(f"DEBUG: parse_books started with query='{query}', source='{source}', fetch_details={fetch_details}")

        # Замеряем время выполнения задачи
        task_start = time.time()

        result = run_async_task()
        
        # Логируем время выполнения задачи
        task_time = time.time() - task_start
        celery_logger.info(f"⏱️ Задача выполнена за: {task_time:.2f} сек")
        
        # ДИАГНОСТИКА: Логируем результат
        celery_logger.info(f"DEBUG: parse_books result = {result}")
        celery_logger.info(f"DEBUG: parse_books result type = {type(result)}")
        
        # Форматируем результат для API
        if isinstance(result, dict):
            books_count = result.get('books_found', 0)
            celery_logger.info(f"Парсинг завершен для запроса '{query}': найдено {books_count} книг")
            celery_logger.info(f"DEBUG: Returning dict result: {result}")
            return result
        else:
            # Старый формат (число)
            celery_logger.info(f"Парсинг завершен для запроса '{query}': найдено {result} книг")
            result_dict = {
                "books_found": result,
                "books_added": result,
                "books_updated": 0,
                "message": f"Парсинг завершен: найдено {result} книг"
            }
            celery_logger.info(f"DEBUG: Returning old format result: {result_dict}")
            return result_dict
            
    except Exception as e:
        celery_logger.error(f"Ошибка парсинга для '{query}': {e}")
        error_result = {
            "books_found": 0,
            "books_added": 0,
            "books_updated": 0,
            "message": f"Ошибка парсинга: {str(e)}"
        }
        celery_logger.info(f"DEBUG: Returning error result: {error_result}")
        # Возвращаем структурированный ответ об ошибке
        return error_result

async def _check_existing_books_in_db(db: AsyncSession, query: str) -> Tuple[bool, List[DBBook], str]:
    """
    Проверяет, есть ли в базе книги, похожие на запрос

    Returns:
        Кортеж (has_exact_match: bool, similar_books: List[DBBook], reason: str)
    """
    try:
        # Ищем книги, похожие на запрос (LIKE поиск)
        search_pattern = f"%{query}%"
        
        result = await db.execute(
            select(DBBook)
            .where(
                or_(
                    DBBook.title.ilike(search_pattern),
                    DBBook.author.ilike(search_pattern)
                )
            )
            .limit(20)
        )
        existing_books = result.scalars().all()

        if not existing_books:
            return False, [], "no_existing_books"
        
        # Проверяем каждую книгу на точное совпадение
        for book in existing_books:
            is_similar, reason = is_book_similar(query, book.title, book.author)
            if is_similar:
                celery_logger.info(f"Найдена похожая книга в БД: {book.title} (причина: {reason})")
                return True, existing_books, reason
        
        return False, existing_books, "similar_books_found"
        
    except Exception as e:
        celery_logger.error(f"Ошибка проверки существующих книг: {e}")
        return False, [], "error_checking"


async def _parse_books_async(query: str, source: str, fetch_details: bool = False):
    """Асинхронная функция парсинга книг с реальным парсером

    Args:
        query: Поисковый запрос
        source: Источник парсинга
        fetch_details: Загружать ли детальную страницу для извлечения характеристик
    """

    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # ШАГ 1: Проверяем нагрузку сервера для определения лимита парсинга
            is_loaded, parse_limit = should_limit_parsing()
            celery_logger.info(f"Лимит парсинга: {parse_limit} (нагрузка: {'высокая' if is_loaded else 'нормальная'})")
            
            # ШАГ 2: Проверяем, есть ли в базе похожие книги
            has_existing, existing_books, match_reason = await _check_existing_books_in_db(db, query)
            
            if has_existing:
                celery_logger.info(f"Найдены существующие книги в БД для запроса '{query}': {len(existing_books)} шт. (причина: {match_reason})")
                
                # Проверяем, есть ли запрос в очереди допарсинга
                needs_more, additional_limit = await check_and_complete_pending_parse(query)
                
                if not needs_more:
                    # Точное совпадение найдено, не парсим
                    celery_logger.info(f"Книги уже есть в БД, пропускаем парсинг для '{query}'")
                    return {
                        "books_found": 0,
                        "books_added": 0,
                        "books_updated": 0,
                        "message": f"Книги уже есть в базе ({match_reason})",
                        "cached": True,
                        "books": [b.to_dict() for b in existing_books[:5]]
                    }
                else:
                    # Нужно допарсить дополнительные книги
                    parse_limit = min(parse_limit, additional_limit)
                    celery_logger.info(f"Допарсинг для '{query}': лимит {parse_limit}")
            
            # ШАГ 3: Проверяем очередь допарсинга
            needs_more, additional_limit = await check_and_complete_pending_parse(query)
            if needs_more:
                parse_limit = min(parse_limit, additional_limit)
                celery_logger.info(f"Допарсинг из очереди: {parse_limit} книг")
            
            # Импортируем реальный парсер
            if source == "chitai-gorod":
                try:
                    # Правильный импорт парсера
                    from parsers.chitai_gorod import ChitaiGorodParser
                    parser = ChitaiGorodParser()
                    celery_logger.info(f"Парсер успешно импортирован: {parser}")
                except ImportError as e:
                    celery_logger.error(f"Не удалось импортировать парсер: {e}")
                    # Создаем заглушку для демонстрации
                    parser = MockParser()
            else:
                raise ValueError(f"Неподдерживаемый источник: {source}")
            
            celery_logger.info(f"Начинаем парсинг для запроса: '{query}' (fetch_details={fetch_details}, limit={parse_limit})")

            # 🔍 ОТЛАДКА: Проверяем парсер
            celery_logger.info(f"🔍 ОТЛАДКА: parser type = {type(parser)}")
            celery_logger.info(f"🔍 ОТЛАДКА: parser class = {parser.__class__.__name__}")
            
            # Замеряем время парсинга
            parse_start = time.time()

            # Ищем книги с правильными параметрами
            books = await parser.search_books(query, max_pages=1, limit=parse_limit, fetch_details=fetch_details)

            # Логируем время парсинга
            parse_time = time.time() - parse_start
            celery_logger.info(f"⏱️ Парсинг занял: {parse_time:.2f} сек")

            # 🔍 ОТЛАДКА: Проверяем результат парсера
            celery_logger.info(f"🔍 ОТЛАДКА: books = {books}")
            celery_logger.info(f"🔍 ОТЛАДКА: type(books) = {type(books)}")
            celery_logger.info(f"🔍 ОТЛАДКА: len(books) = {len(books) if books else 'None'}")
            
            if not books:
                celery_logger.info(f"Книги не найдены для запроса: '{query}'")
                await _log_parsing_result(db, source, "no_results", f"Книги не найдены для запроса: {query}")
                return {
                    "books_found": 0,
                    "books_added": 0,
                    "books_updated": 0,
                    "message": f"Книги не найдены для запроса: {query}"
                }
            
            # Сохраняем найденные книги в БД
            saved_count = 0
            updated_count = 0
            
            for book in books:
                try:
                    await _save_book(db, book)
                    saved_count += 1
                    
                    # Логируем каждую найденную книгу
                    celery_logger.info(f"Найдена книга: {book.title} - {book.current_price} руб. (скидка {book.discount_percent}%)")
                    if fetch_details:
                        celery_logger.info(f"  Характеристики: publisher={book.publisher}, binding={book.binding}, genres={book.genres}")
                    
                except Exception as book_error:
                    celery_logger.error(f"Ошибка сохранения книги {book.title}: {book_error}")
                    continue
            
            # ШАГ 4: Добавляем ВСЕ найденные книги в Google Sheets (топ-5 по цене)
            if books:
                await _add_to_sheets_batch(books)
            
            # ШАГ 5: Если парсили с лимитом и книг больше, чем сохранили - добавляем в очередь допарсинга
            # (это значит, что есть еще книги для этого автора/запроса)
            if is_loaded and len(books) >= parse_limit:
                author = books[0].author if books else None
                await add_to_pending_parse(query, author, len(books))
                celery_logger.info(f"Добавлено в очередь допарсинга: {query} (автор: {author})")
            
            # Логируем результат парсинга
            await _log_parsing_result(db, source, "success", 
                                    f"Парсинг '{query}': найдено {len(books)} книг, сохранено {saved_count}")
            
            return {
                "books_found": len(books),
                "books_added": saved_count,
                "books_updated": updated_count,
                "message": f"Парсинг завершен: найдено {len(books)} книг, сохранено {saved_count}",
                "limit_used": parse_limit,
                "was_loaded": is_loaded
            }
            
        except Exception as e:
            celery_logger.error(f"Ошибка асинхронного парсинга: {e}")
            await _log_parsing_result(db, source, "error", str(e))
            return {
                "books_found": 0,
                "books_added": 0,
                "books_updated": 0,
                "message": f"Ошибка парсинга: {str(e)}"
            }

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 2})
def scan_discounts(self):
    """Периодическое сканирование акционных книг"""
    
    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_scan_discounts_async())
        finally:
            loop.close()
    
    try:
        result = run_async_task()
        celery_logger.info(f"Сканирование скидок завершено. Найдено акционных книг: {result}")
        return result
    except Exception as e:
        celery_logger.error(f"Ошибка при сканировании скидок: {e}")
        raise self.retry(countdown=900, exc=e)

async def _scan_discounts_async():
    """Асинхронное сканирование акционных книг"""
    
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            try:
                import sys
                import os
                # Добавляем корневую папку в PYTHONPATH
                current_dir = os.path.dirname(os.path.abspath(__file__))
                root_dir = os.path.dirname(os.path.dirname(current_dir))
                if root_dir not in sys.path:
                    sys.path.append(root_dir)
                
                from parsers.chitai_gorod import ChitaiGorodParser
                parser = ChitaiGorodParser()
            except ImportError as e:
                celery_logger.warning(f"Не удалось импортировать парсер: {e}")
                # Создаем заглушку для демонстрации
                parser = MockParser()
            
            celery_logger.info("Начинаем сканирование акционных книг")
            
            # Сканируем акционные книги
            discount_books = await parser.check_discounts()
            
            if not discount_books:
                celery_logger.info("Акционные книги не найдены")
                await _log_parsing_result(db, "chitai-gorod", "no_discounts", "Акционные книги не найдены")
                return 0
            
            # Сохраняем акционные книги
            saved_count = 0
            high_discount_books = []
            
            for book in discount_books:
                await _save_book(db, book)
                await _add_to_sheets(book)
                saved_count += 1
                
                # Выделяем книги с высокими скидками
                if book.discount_percent and book.discount_percent >= 30:
                    high_discount_books.append(book)
                
                celery_logger.info(f"Акционная книга: {book.title} - {book.current_price} руб. (скидка {book.discount_percent}%)")
            
            # Отправляем уведомления о книгах с высокими скидками всем пользователям
            if high_discount_books:
                await _notify_high_discount_books(high_discount_books)
            
            # Логируем результат
            await _log_parsing_result(db, "chitai-gorod", "discounts_found", 
                                    f"Сканирование скидок: найдено {len(discount_books)} акционных книг, сохранено {saved_count}")
            
            return len(discount_books)
            
        except Exception as e:
            celery_logger.error(f"Ошибка сканирования скидок: {e}")
            await _log_parsing_result(db, "chitai-gorod", "discounts_error", str(e))
            return 0

async def _notify_high_discount_books(high_discount_books: list):
    """Уведомление пользователей о книгах с высокими скидками"""
    
    try:
        from app.bot.telegram_bot import TelegramBot
        bot = TelegramBot()
        
        # Получаем всех пользователей
        session_factory = get_session_factory()
        async with session_factory() as db:
            result = await db.execute(select(User))
            users = result.scalars().all()
            
            for user in users:
                try:
                    # Отправляем топ-3 книги с высокими скидками
                    top_books = sorted(high_discount_books, key=lambda x: x.discount_percent or 0, reverse=True)[:3]
                    
                    message = "🔥 <b>Отличные скидки на книги!</b>\n\n"
                    
                    for i, book in enumerate(top_books, 1):
                        message += f"{i}. <b>{book.title}</b>\n"
                        if book.author:
                            message += f"   👤 {book.author}\n"
                        message += f"   💰 <b>{book.current_price} руб.</b>\n"
                        if book.original_price:
                            message += f"   💸 <s>{book.original_price} руб.</s>\n"
                        message += f"   🔥 <b>Скидка {book.discount_percent}%</b>\n"
                        message += f"   🔗 <a href='{book.url}'>Ссылка</a>\n\n"
                    
                    message += "💡 Подпишитесь на уведомления для получения персональных рекомендаций!"
                    
                    await bot.send_message(user.telegram_id, message)
                    
                except Exception as e:
                    celery_logger.error(f"Ошибка отправки уведомления пользователю {user.id}: {e}")
                    continue
                
                # Небольшая задержка между отправками
                await asyncio.sleep(1)
                
    except Exception as e:
        celery_logger.error(f"Ошибка уведомления о высоких скидках: {e}")

@celery_app.task
def update_popular_books():
    """Обновление базы популярных книг"""
    
    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_update_popular_books_async())
        finally:
            loop.close()
    
    try:
        result = run_async_task()
        celery_logger.info(f"Обновление популярных книг завершено. Обработано категорий: {result}")
        return result
    except Exception as e:
        celery_logger.error(f"Ошибка обновления популярных книг: {e}")
        raise

async def _update_popular_books_async():
    """Асинхронное обновление популярных книг"""
    
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            from parsers.chitai_gorod import ChitaiGorodParser
            parser = ChitaiGorodParser()
            
            # Популярные категории для сканирования
            popular_categories = [
                "программирование", "python", "javascript", "java", 
                "математика", "бизнес", "психология", "философия",
                "история", "литература", "наука"
            ]
            
            processed_categories = 0
            
            for category in popular_categories:
                try:
                    celery_logger.info(f"Обновляем категорию: {category}")
                    
                    books = await parser.search_books(category)
                    
                    # Сохраняем только лучшие книги из категории
                    if books:
                        # Берем топ-10 книг по скидке
                        best_books = sorted(books, key=lambda x: x.discount_percent or 0, reverse=True)[:10]
                        
                        for book in best_books:
                            await _save_book(db, book)
                            await _add_to_sheets(book)
                        
                        celery_logger.info(f"Обновлена категория '{category}': сохранено {len(best_books)} книг")
                    
                    processed_categories += 1
                    
                    # Задержка между категориями
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    celery_logger.error(f"Ошибка обновления категории '{category}': {e}")
                    continue
            
            await _log_parsing_result(db, "popular_books", "success", 
                                    f"Обновление популярных книг: обработано {processed_categories} категорий")
            
            return processed_categories
            
        except Exception as e:
            celery_logger.error(f"Ошибка обновления популярных книг: {e}")
            return 0


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 300})
def update_chitai_gorod_token(self):
    """Обновление токена авторизации Читай-города через FlareSolverr

    Эта задача:
    1. Запрашивает страницу Читай-города через FlareSolverr
    2. Извлекает токен из cookies
    3. Сохраняет токен в Redis
    4. Проверяет работоспособность токена

    Запускается:
    - По расписанию (каждые 3 часа)
    - При обнаружении 401 ошибки в парсере
    """
    import requests
    import re
    from dotenv import load_dotenv

    load_dotenv()

    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_update_chitai_gorod_token_async())
        finally:
            loop.close()

    try:
        celery_logger.info("Начинаем обновление токена Читай-города через FlareSolverr")
        result = run_async_task()
        celery_logger.info(f"Обновление токена завершено: {result}")
        return result
    except Exception as e:
        celery_logger.error(f"Ошибка при обновлении токена Читай-города: {e}")
        raise self.retry(countdown=600, exc=e)


async def _update_chitai_gorod_token_async():
    """Асинхронное обновление токена Читай-города"""

    import requests
    import re
    import json
    from dotenv import load_dotenv

    load_dotenv()

    try:
        # Получаем URL FlareSolverr из переменных окружения
        flaresolverr_url = os.getenv("FLARESOLVERR_URL", "http://flaresolverr:8191/v1")
        celery_logger.info(f"Используем FlareSolverr: {flaresolverr_url}")

        # Формируем запрос к FlareSolverr
        flaresolverr_request = {
            "cmd": "request.get",
            "url": "https://www.chitai-gorod.ru",
            "maxTimeout": 60000,  # 60 секунд
            "disableMedia": True  # Отключаем загрузку изображений и медиа
        }

        celery_logger.info("Отправляем запрос к FlareSolverr...")
        response = requests.post(
            flaresolverr_url,
            json=flaresolverr_request,
            timeout=90  # Увеличиваем таймаут
        )

        if response.status_code != 200:
            celery_logger.error(f"FlareSolverr вернул ошибку: {response.status_code}")
            return {"status": "error", "message": f"FlareSolverr error: {response.status_code}"}

        data = response.json()

        if data.get("status") != "ok":
            celery_logger.error(f"FlareSolverr вернул неуспешный статус: {data}")
            return {"status": "error", "message": f"FlareSolverr status: {data.get('status')}"}

        # Извлекаем токен из cookies
        solution = data.get("solution", {})
        cookies = solution.get("cookies", [])

        # Отладка: логируем все cookies
        celery_logger.info(f"Получено {len(cookies)} cookies:")
        for cookie in cookies:
            cookie_name = cookie.get("name", "")
            cookie_value = cookie.get("value", "")
            # Логируем имя и первые 50 символов значения
            if len(cookie_value) > 50:
                cookie_value = cookie_value[:50] + "..."
            celery_logger.info(f"  - {cookie_name}: {cookie_value}")

        token = None
        for cookie in cookies:
            # Ищем access-token (или bearer_token как fallback)
            cookie_name = cookie.get("name", "")
            if cookie_name == "access-token" or cookie_name == "bearer_token":
                token = cookie.get("value")
                # Декодируем URL-encoded значение (например, %20 -> пробел)
                from urllib.parse import unquote
                token = unquote(token)
                # Убираем префикс "Bearer " если он есть
                if token.startswith("Bearer "):
                    token = token[7:]  # Убираем "Bearer "
                celery_logger.info(f"Токен найден в cookie '{cookie_name}'")
                break

        if not token:
            celery_logger.error("Токен не найден в cookies")
            # Попробуем найти токен с другими именами
            for cookie in cookies:
                cookie_name = cookie.get("name", "").lower()
                if "token" in cookie_name or "bearer" in cookie_name:
                    celery_logger.info(f"Найден потенциальный токен: {cookie.get('name')} = {cookie.get('value')[:50]}...")

            # Отправляем уведомление об ошибке
            try:
                from services.token_manager import get_token_manager
                token_manager = get_token_manager()
                token_manager.send_token_notification(
                    "error",
                    "❌ Токен не найден в cookies при обновлении через FlareSolverr",
                    "FlareSolverr вернул cookies, но access-token не найден"
                )
            except Exception as notify_error:
                celery_logger.error(f"Ошибка отправки уведомления: {notify_error}")

            return {"status": "error", "message": "Token not found in cookies"}

        celery_logger.info(f"Токен извлечен: {token[:20]}...")

        # Проверяем работоспособность токена
        celery_logger.info("Проверяем работоспособность токена...")

        user_id = os.getenv("CHITAI_GOROD_USER_ID")
        if not user_id:
            celery_logger.warning("CHITAI_GOROD_USER_ID не задан, используем дефолтный")
            user_id = "00000000-0000-0000-0000-000000000000"

        api_url = "https://web-agr.chitai-gorod.ru/web/api/v2/search/product"
        headers = {
            "accept": "*/*",
            "accept-language": "ru,en;q=0.9",
            "authorization": f"Bearer {token}",
            "initial-feature": "index",
            "platform": "desktop",
            "shop-brand": "chitaiGorod",
            "user-id": user_id,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 YaBrowser/25.12.0.0 Yowser/2.5",
        }
        params = {
            "customerCityId": "39",
            "products[page]": "1",
            "products[per-page]": "1",
            "phrase": "python"
        }

        check_response = requests.get(api_url, headers=headers, params=params, timeout=30)

        # Определяем, был ли запрос успешным
        success_response = None

        if check_response.status_code == 200:
            celery_logger.info("Токен работает корректно!")
            success_response = check_response

        elif check_response.status_code == 401:
            celery_logger.error("Токен недействителен (401)")

            # Отправляем уведомление об ошибке
            try:
                from services.token_manager import get_token_manager
                token_manager = get_token_manager()
                token_manager.send_token_notification(
                    "error",
                    "❌ Токен недействителен (401)",
                    f"Токен: {token[:30]}...\nAPI вернул ошибку авторизации"
                )
            except Exception as notify_error:
                celery_logger.error(f"Ошибка отправки уведомления: {notify_error}")

            return {"status": "error", "message": "Token is invalid (401)"}

        elif check_response.status_code == 403:
            # 403 - возможно, нужны дополнительные cookies
            celery_logger.error("Ошибка 403 Forbidden")
            try:
                error_data = check_response.json()
                celery_logger.error(f"Ответ API: {error_data}")
            except:
                celery_logger.error(f"Текст ответа: {check_response.text[:500]}")

            # Попробуем передать все cookies вместе с токеном
            celery_logger.info("Пробуем передать все cookies вместе с токеном...")

            # Создаем словарь cookies
            cookies_dict = {}
            for cookie in cookies:
                cookies_dict[cookie.get("name")] = cookie.get("value")

            # Повторяем запрос с cookies
            check_response_with_cookies = requests.get(
                api_url,
                headers=headers,
                params=params,
                cookies=cookies_dict,
                timeout=30
            )

            if check_response_with_cookies.status_code == 200:
                celery_logger.info("Токен работает с cookies!")
                success_response = check_response_with_cookies
            else:
                celery_logger.error(f"С cookies тоже не работает: {check_response_with_cookies.status_code}")
                try:
                    error_data = check_response_with_cookies.json()
                    celery_logger.error(f"Ответ API с cookies: {error_data}")
                except:
                    celery_logger.error(f"Текст ответа с cookies: {check_response_with_cookies.text[:500]}")
                return {"status": "error", "message": f"403 even with cookies"}

        else:
            celery_logger.error(f"Неожиданный статус при проверке токена: {check_response.status_code}")
            try:
                error_data = check_response.json()
                celery_logger.error(f"Ответ API: {error_data}")
            except:
                celery_logger.error(f"Текст ответа: {check_response.text[:500]}")

            # Отправляем уведомление об ошибке
            try:
                from services.token_manager import get_token_manager
                token_manager = get_token_manager()
                token_manager.send_token_notification(
                    "error",
                    f"❌ Неожиданный статус при проверке токена: {check_response.status_code}",
                    f"Токен: {token[:30]}...\nAPI вернул неожиданный статус"
                )
            except Exception as notify_error:
                celery_logger.error(f"Ошибка отправки уведомления: {notify_error}")

            return {"status": "error", "message": f"Unexpected status: {check_response.status_code}"}

        # Если запрос был успешным, сохраняем токен
        if success_response and success_response.status_code == 200:
            # Сохраняем токен в Redis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            redis_password = os.getenv("REDIS_PASSWORD")

            if redis_url and redis_password:
                # Формируем URL с паролем
                import re
                redis_pattern = r'redis://:(?P<password>[^@]+)@(?P<host>[^:]+):(?P<port>\d+)/\d+'
                match = re.match(redis_pattern, redis_url)
                if not match:
                    # Формируем правильный URL
                    host = redis_url.split("://")[1].split(":")[0]
                    port = redis_url.split(":")[-1].split("/")[0]
                    redis_url = f"redis://:{redis_password}@{host}:{port}/0"

                try:
                    import redis
                    redis_client = redis.from_url(redis_url, decode_responses=True)
                    redis_client.setex(
                        "chitai_gorod_token",
                        86400,  # 24 часа TTL
                        token
                    )
                    redis_client.close()
                    celery_logger.info("Токен сохранен в Redis (TTL: 24 часа)")
                except Exception as redis_error:
                    celery_logger.error(f"Ошибка сохранения в Redis: {redis_error}")
                    # Продолжаем даже если Redis недоступен

            # Сохраняем cookies в Redis (если запрос был успешен с cookies)
            if success_response and success_response.status_code == 200:
                try:
                    from services.token_manager import get_token_manager
                    token_manager = get_token_manager()

                    # Создаем словарь cookies
                    cookies_dict = {}
                    for cookie in cookies:
                        cookies_dict[cookie.get("name")] = cookie.get("value")

                    # Сохраняем cookies
                    token_manager.save_chitai_gorod_cookies(cookies_dict, ttl=86400)
                    celery_logger.info(f"Cookies сохранены в Redis: {len(cookies_dict)} cookies")
                except Exception as cookies_error:
                    celery_logger.error(f"Ошибка сохранения cookies: {cookies_error}")

            # Также обновляем .env файл
            env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
            try:
                with open(env_file, "r") as f:
                    env_lines = f.readlines()

                # Обновляем токен в .env
                with open(env_file, "w") as f:
                    for line in env_lines:
                        if line.startswith("CHITAI_GOROD_BEARER_TOKEN="):
                            f.write(f'CHITAI_GOROD_BEARER_TOKEN="{token}"\n')
                        else:
                            f.write(line)

                celery_logger.info("Токен обновлен в .env файле")
            except Exception as env_error:
                celery_logger.error(f"Ошибка обновления .env: {env_error}")

            # Отправляем уведомление об успешном обновлении
            try:
                from services.token_manager import get_token_manager
                token_manager = get_token_manager()
                token_manager.send_token_notification(
                    "success",
                    "✅ Токен Читай-города успешно обновлён",
                    f"Токен: {token[:30]}...\nСохранён в Redis на 24 часа"
                )
            except Exception as notify_error:
                celery_logger.error(f"Ошибка отправки уведомления: {notify_error}")

            return {
                "status": "success",
                "message": "Token updated successfully",
                "token_preview": f"{token[:20]}..."
            }

    except requests.Timeout:
        celery_logger.error("Таймаут при запросе к FlareSolverr")

        # Отправляем уведомление об ошибке
        try:
            from services.token_manager import get_token_manager
            token_manager = get_token_manager()
            token_manager.send_token_notification(
                "error",
                "❌ Таймаут при запросе к FlareSolverr",
                "FlareSolverr не ответил вовремя (таймаут 90 сек)"
            )
        except Exception as notify_error:
            celery_logger.error(f"Ошибка отправки уведомления: {notify_error}")

        return {"status": "error", "message": "FlareSolverr timeout"}
    except Exception as e:
        celery_logger.error(f"Ошибка при обновлении токена: {e}")

        # Отправляем уведомление об ошибке
        try:
            from services.token_manager import get_token_manager
            token_manager = get_token_manager()
            token_manager.send_token_notification(
                "error",
                "❌ Ошибка при обновлении токена",
                f"Ошибка: {str(e)}"
            )
        except Exception as notify_error:
            celery_logger.error(f"Ошибка отправки уведомления: {notify_error}")

        return {"status": "error", "message": str(e)}


# =============================================================================
# Задача проверки подписок по ценам с парсингом (каждые 4 часа)
# =============================================================================

def check_subscriptions_prices():
    """
    Проверка активных подписок по ценам с реальным парсингом книг.
    Для каждой подписки с book_id - парсим книгу по source_id для получения актуальной цены.
    Если цена книги соответствует условиям подписки - отправляем уведомление и деактивируем подписку.
    """
    
    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_check_subscriptions_prices_async())
        finally:
            loop.close()
    
    try:
        result = run_async_task()
        celery_logger.info(f"Проверка цен подписок завершена. Уведомлений отправлено: {result}")
        return result
    except Exception as e:
        celery_logger.error(f"Ошибка при проверке цен подписок: {e}")
        celery_logger.error(traceback.format_exc())
        raise

# Регистрируем задачу
check_subscriptions_prices_task = celery_app.task(
    check_subscriptions_prices, 
    bind=True, 
    autoretry_for=(Exception,), 
    retry_kwargs={'max_retries': 3}
)

async def _check_subscriptions_prices_async():
    """
    Асинхронная функция проверки цен подписок с реальным парсингом.
    Для каждой подписки с book_id:
    1. Находит книгу в БД
    2. Парсит книгу по source_id для получения актуальной цены
    3. Проверяет условия подписки
    4. Отправляет уведомление и деактивирует подписку при совпадении
    """
    
    import time
    start_time = time.time()
    errors = []
    total_checked = 0
    active_count = 0
    matched_count = 0
    
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # Импортируем парсер
            try:
                import sys
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                root_dir = os.path.dirname(os.path.dirname(current_dir))
                if root_dir not in sys.path:
                    sys.path.append(root_dir)
                
                from parsers.chitai_gorod import ChitaiGorodParser
                parser = ChitaiGorodParser()
            except ImportError as e:
                celery_logger.warning(f"Не удалось импортировать парсер: {e}")
                parser = MockParser()
            
            # Получаем все активные подписки с book_id
            result = await db.execute(
                select(Alert).where(
                    and_(
                        Alert.is_active == True,
                        Alert.book_id != None
                    )
                )
            )
            alerts = result.scalars().all()
            
            if not alerts:
                celery_logger.info("Нет активных подписок с book_id для проверки цен")
                return 0
            
            celery_logger.info(f"Начинаем проверку цен для {len(alerts)} подписок")
            
            total_checked = len(alerts)
            active_count = total_checked
            notifications_sent = 0
            matched_count = 0
            
            for alert in alerts:
                try:
                    # Находим книгу в БД по book_id
                    book_result = await db.execute(
                        select(DBBook).where(DBBook.id == alert.book_id)
                    )
                    db_book = book_result.scalar_one_or_none()
                    
                    if not db_book:
                        celery_logger.warning(f"Книга {alert.book_id} не найдена в БД для подписки {alert.id}")
                        continue
                    
                    celery_logger.info(f"Проверяем подписку {alert.id}: {db_book.title} (source_id: {db_book.source_id})")
                    
                    # Парсим книгу по source_id для получения актуальной цены
                    # Используем source_id как поисковый запрос
                    try:
                        parsed_books = await parser.search_books(
                            db_book.source_id, 
                            max_pages=1, 
                            limit=1
                        )
                    except Exception as parse_error:
                        celery_logger.error(f"Ошибка парсинга для {db_book.source_id}: {parse_error}")
                        parsed_books = []
                    
                    if not parsed_books:
                        celery_logger.info(f"Не удалось получить актуальные данные для книги: {db_book.title}")
                        continue
                    
                    # Берём первую найденную книгу (она должна соответствовать source_id)
                    parsed_book = parsed_books[0]
                    
                    celery_logger.info(
                        f"Актуальная цена для {parsed_book.title}: {parsed_book.current_price}₽ "
                        f"(скидка {parsed_book.discount_percent}%)"
                    )
                    
                    # Проверяем условия подписки
                    price_match = True
                    if alert.target_price and parsed_book.current_price > float(alert.target_price):
                        price_match = False
                    
                    discount_match = True
                    if alert.min_discount and (parsed_book.discount_percent or 0) < alert.min_discount:
                        discount_match = False
                    
                    # Если оба условия выполняются
                    if price_match and discount_match:
                        celery_logger.info(
                            f"✅ Найдена книга по подписке {alert.id}: {parsed_book.title} - "
                            f"{parsed_book.current_price}₽ (скидка {parsed_book.discount_percent}%)"
                        )
                        
                        matched_count += 1
                        
                        # Обновляем цену в БД
                        db_book.current_price = parsed_book.current_price
                        db_book.original_price = parsed_book.original_price
                        db_book.discount_percent = parsed_book.discount_percent
                        db_book.parsed_at = parsed_book.parsed_at
                        await db.commit()
                        
                        # Отправляем уведомление
                        await _send_subscription_notification_from_parser(db, alert, parsed_book, db_book)
                        
                        # Деактивируем подписку
                        alert.is_active = False
                        alert.updated_at = datetime.now()
                        await db.commit()
                        
                        notifications_sent += 1
                        celery_logger.info(f"Подписка {alert.id} деактивирована после уведомления")
                    else:
                        celery_logger.info(
                            f"Книга {parsed_book.title} не соответствует условиям подписки: "
                            f"цена={parsed_book.current_price}₽ (нужно<={alert.target_price}), "
                            f"скидка={parsed_book.discount_percent}% (нужно>={alert.min_discount}%)"
                        )
                    
                    # Задержка между запросами
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    celery_logger.error(f"Ошибка обработки подписки {alert.id}: {e}")
                    errors.append(f"Подписка {alert.id}: {str(e)}")
                    continue
            
            # Вычисляем время выполнения
            duration = time.time() - start_time
            
            celery_logger.info(f"Проверка цен подписок завершена. Отправлено уведомлений: {notifications_sent}")
            
            # Отправляем статистику в Telegram бот
            try:
                from services.token_manager import get_token_manager
                token_manager = get_token_manager()
                token_manager.send_subscriptions_check_notification(
                    total_checked=total_checked,
                    active_count=active_count,
                    matched_count=matched_count,
                    deactivated_count=notifications_sent,
                    notifications_sent=notifications_sent,
                    duration_seconds=duration,
                    errors="\n".join(errors) if errors else None
                )
            except Exception as notify_error:
                celery_logger.error(f"Ошибка отправки статистики: {notify_error}")
            
            return notifications_sent
            
        except Exception as e:
            celery_logger.error(f"Критическая ошибка при проверке цен подписок: {e}")
            raise

async def _send_subscription_notification_from_parser(db: AsyncSession, alert: Alert, parsed_book: ParserBook, db_book: DBBook):
    """
    Отправка уведомления о книге по подписке (с данными из парсера).
    Формат сообщения:
    🔔 Книга поступила в продажу!
    
    📖 Остров привидений
    ✍️ Автор: Артур Конан Дойл
    💰 Цена: 299 ₽ (было 450 ₽, скидка 33%)
    🎯 Ваше условие: до 300 ₽
    
    👉 Купить: [ссылка]
    """
    
    try:
        # Получаем пользователя
        result = await db.execute(select(User).where(User.id == alert.user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            celery_logger.error(f"Пользователь {alert.user_id} не найден")
            return
        
        # Формируем сообщение
        message = "🔔 <b>Книга поступила в продажу!</b>\n\n"
        message += f"📖 <b>{parsed_book.title}</b>\n"
        
        if parsed_book.author:
            message += f"✍️ Автор: {parsed_book.author}\n"
        
        # Цена и скидка
        if parsed_book.original_price and parsed_book.original_price > parsed_book.current_price:
            discount = int((1 - parsed_book.current_price / parsed_book.original_price) * 100)
            message += f"💰 Цена: <b>{int(parsed_book.current_price)} ₽</b> (было {int(parsed_book.original_price)} ₽, скидка {discount}%)\n"
        else:
            message += f"💰 Цена: <b>{int(parsed_book.current_price)} ₽</b>\n"
        
        # Условие подписки
        if alert.target_price:
            message += f"🎯 Ваше условие: до {int(alert.target_price)} ₽\n"
        elif alert.min_discount:
            message += f"🎯 Ваше условие: скидка от {int(alert.min_discount)}%\n"
        
        # Ссылка на книгу
        if parsed_book.url:
            message += f"\n👉 <a href='{parsed_book.url}'>Купить</a>"
        
        # Отправляем через Telegram Bot
        try:
            from app.bot.telegram_bot import TelegramBot
            bot = TelegramBot()
            await bot.send_message(user.telegram_id, message)
            celery_logger.info(f"Уведомление отправлено пользователю {user.telegram_id} для книги {parsed_book.title}")
        except Exception as bot_error:
            celery_logger.error(f"Ошибка отправки Telegram уведомления: {bot_error}")
        
        # Создаем запись в таблице уведомлений
        try:
            notification = Notification(
                user_id=user.id,
                book_id=db_book.id,
                alert_id=alert.id,
                title=parsed_book.title,
                author=parsed_book.author,
                current_price=parsed_book.current_price,
                original_price=parsed_book.original_price,
                discount_percent=parsed_book.discount_percent,
                url=parsed_book.url,
                image_url=parsed_book.image_url
            )
            db.add(notification)
            await db.commit()
        except Exception as notify_error:
            celery_logger.error(f"Ошибка создания записи уведомления: {notify_error}")
            await db.rollback()
        
    except Exception as e:
        celery_logger.error(f"Ошибка отправки уведомления подписки: {e}")
        await db.rollback()

