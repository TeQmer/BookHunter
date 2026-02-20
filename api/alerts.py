from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional
from datetime import datetime

from database.config import get_db
from models.alert import Alert
from models.notification import Notification
from models.book import Book
from services.logger import api_logger as logger

router = APIRouter()

__all__ = ["router"]

# ========== ВАЛИДАЦИЯ ВХОДНЫХ ДАННЫХ ==========

def validate_price(value):
    """Валидация цены"""
    if value is None:
        return None
    try:
        price = float(value)
        if price < 0:
            raise HTTPException(status_code=400, detail="Цена не может быть отрицательной")
        if price > 100000:  # Максимальная цена 100 000 ₽
            raise HTTPException(status_code=400, detail="Слишком высокая цена")
        return price
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Неверный формат цены")

def validate_discount(value):
    """Валидация скидки"""
    if value is None:
        return None
    try:
        discount = float(value)
        if discount < 0:
            raise HTTPException(status_code=400, detail="Скидка не может быть отрицательной")
        if discount > 100:
            raise HTTPException(status_code=400, detail="Скидка не может превышать 100%")
        return discount
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Неверный формат скидки")

def validate_string_field(value, field_name, max_length=500):
    """Валидация строковых полей"""
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{field_name} должно быть строкой")
    value = value.strip()
    if len(value) > max_length:
        raise HTTPException(status_code=400, detail=f"{field_name} слишком длинное (максимум {max_length} символов)")
    return value if value else None

def validate_user_id(user_id):
    """Валидация ID пользователя"""
    if user_id is None:
        raise HTTPException(status_code=400, detail="ID пользователя обязателен")
    try:
        uid = int(user_id)
        if uid <= 0:
            raise HTTPException(status_code=400, detail="ID пользователя должен быть положительным числом")
        return uid
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Неверный формат ID пользователя")

@router.get("/", response_model=List[dict])
async def get_alerts(
    db: AsyncSession = Depends(get_db),
    telegram_id: Optional[int] = Query(None, description="Telegram ID пользователя"),
    active_only: bool = Query(True, description="Только активные подписки")
):
    """Получение списка подписок пользователя"""
    
    try:
        # Ищем пользователя по telegram_id
        if telegram_id:
            from models.user import User
            user_result = await db.execute(select(User).where(User.telegram_id == telegram_id))
            user = user_result.scalar_one_or_none()

            if not user:
                return []  # Пользователь не найден, возвращаем пустой список

            user_id = user.id
        else:
            user_id = None

        query = select(Alert)

        if active_only:
            query = query.where(Alert.is_active == True)

        if user_id:
            query = query.where(Alert.user_id == user_id)

        query = query.order_by(Alert.created_at.desc())

        result = await db.execute(query)
        alerts = result.scalars().all()

        return [
            {
                "id": alert.id,
                "user_id": alert.user_id,
                "book_id": alert.book_id,
                "book_title": alert.book_title,
                "book_author": alert.book_author,
                "book_source": alert.book_source,
                "target_price": alert.target_price,
                "min_discount": alert.min_discount,
                "is_active": alert.is_active,
                "notification_type": alert.notification_type,
                "matches_found": alert.matches_found,
                "notifications_sent": alert.notifications_sent,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
                "updated_at": alert.updated_at.isoformat() if alert.updated_at else None,
                "expires_at": alert.expires_at.isoformat() if alert.expires_at else None,
                "notes": alert.notes,
                "search_query": alert.search_query,
                "last_notification": alert.last_notification.isoformat() if alert.last_notification else None
            }
            for alert in alerts
        ]

    except Exception as e:
        logger.error(f"Ошибка получения подписок: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения подписок")

@router.post("/")
async def create_alert(
    alert_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """Создание новой подписки"""
    
    try:
        # Получаем telegram_id и находим пользователя
        telegram_id = alert_data.get("telegram_id")
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Telegram ID обязателен")

        from models.user import User
        user_result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        user_id = user.id

        # Валидация входных данных
        target_price = validate_price(alert_data.get("target_price"))
        min_discount = validate_discount(alert_data.get("min_discount"))
        book_title = validate_string_field(alert_data.get("book_title"), "Название книги", 500)
        book_author = validate_string_field(alert_data.get("book_author"), "Автор книги", 300)
        book_source = validate_string_field(alert_data.get("book_source"), "Источник", 100)
        notification_type = validate_string_field(alert_data.get("notification_type"), "Тип уведомления", 50)

        # Проверяем, что указана хотя бы цена или скидка
        if target_price is None and min_discount is None:
            raise HTTPException(status_code=400, detail="Необходимо указать целевую цену или минимальную скидку")

        # Проверяем book_id
        book_id = alert_data.get("book_id")
        if book_id is not None:
            try:
                book_id = int(book_id)
                if book_id <= 0:
                    raise HTTPException(status_code=400, detail="ID книги должен быть положительным числом")
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Неверный формат ID книги")

        # Создаем новую подписку
        new_alert = Alert(
            user_id=user_id,
            book_id=book_id,
            book_title=book_title or "",
            book_author=book_author,
            book_source=book_source or "chitai-gorod",
            target_price=target_price,
            min_discount=min_discount,
            is_active=True,
            notification_type=notification_type or "price_drop",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            search_query=f"{book_title or ''} {book_author or ''}".strip()
        )
        
        db.add(new_alert)
        await db.commit()
        await db.refresh(new_alert)
        
        # Обновляем счетчик подписок пользователя
        user.total_alerts = (user.total_alerts or 0) + 1
        await db.commit()
        
        logger.info(f"Создана новая подписка: {new_alert.book_title}")

        return {
            "id": new_alert.id,
            "message": "Подписка создана успешно"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка создания подписки: {e}")
        raise HTTPException(status_code=500, detail="Ошибка создания подписки")

@router.put("/{alert_id}")
async def update_alert(
    alert_id: int,
    alert_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """Обновление подписки"""
    
    try:
        result = await db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        
        if not alert:
            raise HTTPException(status_code=404, detail="Подписка не найдена")
        
        # Валидация обновляемых полей
        if "target_price" in alert_data:
            alert.target_price = validate_price(alert_data["target_price"])

        if "min_discount" in alert_data:
            alert.min_discount = validate_discount(alert_data["min_discount"])

        if "book_title" in alert_data:
            alert.book_title = validate_string_field(alert_data["book_title"], "Название книги", 500) or alert.book_title

        if "book_author" in alert_data:
            alert.book_author = validate_string_field(alert_data["book_author"], "Автор книги", 300)

        if "book_source" in alert_data:
            alert.book_source = validate_string_field(alert_data["book_source"], "Источник", 100) or alert.book_source

        if "notification_type" in alert_data:
            alert.notification_type = validate_string_field(alert_data["notification_type"], "Тип уведомления", 50) or alert.notification_type

        # Обновляем остальные поля без валидации
        for field, value in alert_data.items():
            if hasattr(alert, field) and field not in ["target_price", "min_discount", "book_title", "book_author", "book_source", "notification_type"]:
                setattr(alert, field, value)
        
        alert.updated_at = datetime.utcnow()
        
        await db.commit()
        
        logger.info(f"Обновлена подписка: {alert.book_title}")
        
        return {
            "id": alert.id,
            "message": "Подписка обновлена успешно"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка обновления подписки: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обновления подписки")

@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Полное удаление подписки из базы данных"""

    try:
        # Получаем подписку
        result = await db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        
        if not alert:
            raise HTTPException(status_code=404, detail="Подписка не найдена")
        
        # Удаляем связанные уведомления
        await db.execute(
            select(Notification).where(Notification.alert_id == alert_id)
        )
        notifications_result = await db.execute(
            select(Notification).where(Notification.alert_id == alert_id)
        )
        notifications = notifications_result.scalars().all()
        
        for notification in notifications:
            await db.delete(notification)

        # Удаляем саму подписку
        await db.delete(alert)

        # Обновляем счетчик подписок пользователя
        from models.user import User
        user_result = await db.execute(select(User).where(User.id == alert.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user.total_alerts = max(0, (user.total_alerts or 0) - 1)

        await db.commit()
        
        logger.info(f"Подписка полностью удалена: {alert.book_title}")

        return {
            "id": alert.id,
            "message": "Подписка удалена успешно"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка удаления подписки: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления подписки")

@router.post("/create-from-book")
async def create_alert_from_book(
    data: dict,
    db: AsyncSession = Depends(get_db)
):
    """Создание подписки из карточки книги"""
    
    try:
        # Получаем telegram_id
        telegram_id = data.get('user_id') or data.get('telegram_id')
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Telegram ID обязателен")

        # Находим пользователя по telegram_id
        from models.user import User
        user_result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Валидация book_id
        try:
            book_id = int(data.get('book_id'))
            if book_id <= 0:
                raise HTTPException(status_code=400, detail="ID книги должен быть положительным числом")
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Неверный формат ID книги")

        # Валидация цены и скидки
        target_price = validate_price(data.get('target_price'))
        min_discount = validate_discount(data.get('min_discount'))

        # Проверяем, что указана хотя бы цена или скидка
        if target_price is None and min_discount is None:
            raise HTTPException(status_code=400, detail="Необходимо указать целевую цену или минимальную скидку")

        # Получаем информацию о книге
        from models import Book
        result = await db.execute(select(Book).where(Book.id == book_id))
        book = result.scalar_one_or_none()
        
        if not book:
            raise HTTPException(status_code=404, detail="Книга не найдена")
        
        # Проверяем, существует ли уже подписка на эту книгу для этого пользователя
        existing_alert = await db.execute(
            select(Alert).where(
                and_(
                    Alert.book_id == book_id,
                    Alert.user_id == user.id,
                    Alert.is_active == True
                )
            )
        )
        
        if existing_alert.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Подписка на эту книгу уже существует")
        
        # Создаем новую подписку
        new_alert = Alert(
            user_id=user.id,
            book_id=book_id,
            book_title=book.title,
            book_author=book.author,
            book_source=book.source,
            target_price=target_price,
            min_discount=min_discount,
            is_active=True,
            notification_type='price_drop',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            search_query=f"{book.title} {book.author or ''}".strip()
        )
        
        db.add(new_alert)
        await db.commit()
        await db.refresh(new_alert)
        
        # Обновляем счетчик подписок пользователя
        user.total_alerts = (user.total_alerts or 0) + 1
        await db.commit()
        
        logger.info(f"Создана подписка на книгу '{book.title}' с целевой ценой {target_price}₽")

        return {
            "success": True,
            "message": "Подписка создана успешно",
            "alert_id": new_alert.id,
            "book_title": book.title,
            "target_price": target_price
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания подписки из книги: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания подписки: {str(e)}")

@router.post("/{alert_id}/toggle")
async def toggle_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Переключение состояния подписки (активна/неактивна)"""
    
    try:
        result = await db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        
        if not alert:
            raise HTTPException(status_code=404, detail="Подписка не найдена")
        
        alert.is_active = not alert.is_active
        alert.updated_at = datetime.utcnow()
        
        await db.commit()
        
        status = "активирована" if alert.is_active else "деактивирована"
        logger.info(f"Подписка {status}: {alert.book_title}")
        
        return {
            "id": alert.id,
            "is_active": alert.is_active,
            "message": f"Подписка {status} успешно"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка переключения подписки: {e}")
        raise HTTPException(status_code=500, detail="Ошибка переключения подписки")

@router.get("/{alert_id}/notifications")
async def get_alert_notifications(
    alert_id: int,
    limit: int = Query(10, description="Количество уведомлений"),
    db: AsyncSession = Depends(get_db)
):
    """Получение уведомлений для подписки"""
    
    try:
        result = await db.execute(
            select(Notification)
            .where(Notification.alert_id == alert_id)
            .order_by(Notification.sent_at.desc())
            .limit(limit)
        )
        notifications = result.scalars().all()
        
        return [
            {
                "id": notification.id,
                "book_title": notification.book_title,
                "book_author": notification.book_author,
                "book_price": notification.book_price,
                "book_discount": notification.book_discount,
                "book_url": notification.book_url,
                "message": notification.message,
                "message_type": notification.message_type,
                "channel": notification.channel,
                "status": notification.status,
                "is_sent": notification.is_sent,
                "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
                "error_message": notification.error_message,
                "retry_count": notification.retry_count,
                "max_retries": notification.max_retries,
                "created_at": notification.created_at.isoformat() if notification.created_at else None
            }
            for notification in notifications
        ]
        
    except Exception as e:
        logger.error(f"Ошибка получения уведомлений: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения уведомлений")

@router.get("/book/{book_id}")
async def get_user_alert_for_book(
    book_id: int,
    telegram_id: Optional[int] = Query(None, description="Telegram ID пользователя"),
    db: AsyncSession = Depends(get_db)
):
    """Получение подписки пользователя на конкретную книгу"""
    try:
        user_id = None

        # Если указан telegram_id, находим пользователя
        if telegram_id:
            from models.user import User
            user_result = await db.execute(select(User).where(User.telegram_id == telegram_id))
            user = user_result.scalar_one_or_none()

            if user:
                user_id = user.id

        # Получаем активную подписку пользователя на книгу
        if user_id:
            result = await db.execute(
                select(Alert).where(
                    and_(
                        Alert.book_id == book_id,
                        Alert.user_id == user_id,
                        Alert.is_active == True
                    )
                )
            )
        else:
            result = await db.execute(
                select(Alert).where(
                    and_(
                        Alert.book_id == book_id,
                        Alert.is_active == True
                    )
                )
            )

        alert = result.scalar_one_or_none()
        
        if alert:
            return {"alert": alert.to_dict()}
        else:
            return {"alert": None}

    except Exception as e:
        logger.error(f"Ошибка получения подписки для книги: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения подписки")

@router.put("/book/{book_id}")
async def update_user_alert_for_book(
    book_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db)
):
    """Обновление подписки пользователя на конкретную книгу"""
    try:
        # Получаем активную подписку пользователя на книгу
        result = await db.execute(
            select(Alert).where(
                and_(
                    Alert.book_id == book_id,
                    Alert.is_active == True
                )
            )
        )
        alert = result.scalar_one_or_none()
        
        if not alert:
            raise HTTPException(status_code=404, detail="Подписка на эту книгу не найдена")
        
        # Валидация и обновление полей подписки
        if 'target_price' in data:
            alert.target_price = validate_price(data['target_price'])

        if 'min_discount' in data:
            alert.min_discount = validate_discount(data['min_discount'])

        # Проверяем, что указана хотя бы цена или скидка
        if alert.target_price is None and alert.min_discount is None:
            raise HTTPException(status_code=400, detail="Необходимо указать целевую цену или минимальную скидку")

        alert.updated_at = datetime.utcnow()
        
        await db.commit()
        
        logger.info(f"Обновлена подписка на книгу '{alert.book_title}'")
        
        return {
            "success": True,
            "message": "Подписка обновлена успешно",
            "alert": alert.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка обновления подписки: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обновления подписки")
