#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка и управление лимитами запросов пользователей
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.user import User
from fastapi import HTTPException, status


class RequestLimitChecker:
    """Класс для проверки и управления лимитами запросов"""

    @staticmethod
    def check_and_increment_request(db: Session, telegram_id: int) -> User:
        """
        Проверяет лимит запросов пользователя и увеличивает счетчик

        Args:
            db: Сессия базы данных
            telegram_id: ID пользователя в Telegram

        Returns:
            User: Обновленный объект пользователя

        Raises:
            HTTPException: Если превышен лимит запросов
        """
        # Получаем пользователя
        user = db.query(User).filter(User.telegram_id == telegram_id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )

        # Проверяем, нужно ли сбросить счетчик (новый день)
        now = datetime.utcnow()
        if user.requests_updated_at is None:
            # Первое использование - устанавливаем текущую дату
            user.requests_updated_at = now
            user.daily_requests_used = 0
        else:
            # Проверяем, прошел ли день
            last_update = user.requests_updated_at
            if last_update.date() < now.date():
                # Новый день - сбрасываем счетчик
                user.daily_requests_used = 0
                user.requests_updated_at = now

        # Проверяем лимит
        if user.daily_requests_used >= user.daily_requests_limit:
            remaining_time = timedelta(days=1) - (now - user.requests_updated_at.replace(hour=0, minute=0, second=0, microsecond=0))
            hours = remaining_time.seconds // 3600
            minutes = (remaining_time.seconds % 3600) // 60

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Лимит запросов исчерпан ({user.daily_requests_limit} в день). "
                       f"Попробуйте снова через {hours}ч {minutes}м."
            )

        # Увеличиваем счетчик
        user.daily_requests_used += 1
        user.updated_at = now
        db.commit()
        db.refresh(user)

        return user

    @staticmethod
    def get_user_stats(db: Session, telegram_id: int) -> dict:
        """
        Получает статистику запросов пользователя

        Args:
            db: Сессия базы данных
            telegram_id: ID пользователя в Telegram

        Returns:
            dict: Статистика запросов
        """
        user = db.query(User).filter(User.telegram_id == telegram_id).first()

        if not user:
            # Если пользователя нет, создаем его
            user = User(
                telegram_id=telegram_id,
                first_name=f"User {telegram_id}",
                is_active=True,
                daily_requests_used=0,
                daily_requests_limit=15,
                requests_updated_at=datetime.utcnow()
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Проверяем, нужно ли сбросить счетчик (новый день)
        now = datetime.utcnow()
        if user.requests_updated_at is None or user.requests_updated_at.date() < now.date():
            user.daily_requests_used = 0
            user.requests_updated_at = now
            db.commit()
            db.refresh(user)

        return {
            "daily_requests_used": user.daily_requests_used or 0,
            "daily_requests_limit": user.daily_requests_limit or 15,
            "requests_remaining": max(0, (user.daily_requests_limit or 15) - (user.daily_requests_used or 0)),
            "requests_updated_at": user.requests_updated_at.isoformat() if user.requests_updated_at else None
        }
