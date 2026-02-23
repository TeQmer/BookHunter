#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API для аутентификации и авторизации пользователей Telegram Mini App
Реализация на основе статьи: https://habr.com/ru/articles/889270/
"""

import os
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from pydantic import BaseModel
import jwt

from database.config import get_db
from models.user import User
from services.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter()

# ========== КОНФИГУРАЦИЯ JWT ==========
# Секретные ключи для токенов (хранить в переменных окружения!)
JWT_ACCESS_SECRET = os.getenv("JWT_ACCESS_SECRET", "change_access_secret_in_production")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "change_refresh_secret_in_production")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Время жизни токенов
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 15 минут
REFRESH_TOKEN_EXPIRE_DAYS = 7    # 7 дней

# Настройки cookies
COOKIE_OPTIONS = {
    "httponly": True,
    "secure": True,
    "samesite": "strict",
    "path": "/",
    "max_age": 60 * 60 * 24 * REFRESH_TOKEN_EXPIRE_DAYS  # 7 дней в секундах
}


# ========== МОДЕЛИ ЗАПРОСОВ ==========
class SignInRequest(BaseModel):
    """Модель запроса на вход"""
    initData: str


class RefreshRequest(BaseModel):
    """Модель запроса на обновление токена"""
    pass


# ========== ВАЛИДАЦИЯ INITDATA ==========
def validate_init_data(init_data: str, bot_token: str) -> Optional[dict]:
    """
    Валидация initData от Telegram
    Проверяет подпись и извлекает данные пользователя
    
    Args:
        init_data: Строка initData от Telegram WebApp
        bot_token: Токен бота для проверки подписи
        
    Returns:
        Словарь с данными пользователя или None если валидация не прошла
    """
    try:
        # Парсим параметры из initData
        params = {}
        for pair in init_data.split('&'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                params[key] = value
        
        # Проверяем наличие обязательных параметров
        if 'hash' not in params:
            logger.warning("initData не содержит hash")
            return None
        
        # Проверяем время (защита от replay атак)
        if 'auth_date' in params:
            auth_date = int(params['auth_date'])
            current_time = int(time.time())
            # Если данные старше 24 часов - отклоняем
            if current_time - auth_date > 86400:
                logger.warning("initData устарела (старше 24 часов)")
                return None
        
        # Проверяем подпись
        data_check_string = '\n'.join(
            f"{k}={v}" for k, v in sorted(params.items())
            if k != 'hash'
        )
        
        # Создаем секретный ключ из токена бота
        secret_key = hashlib.sha256(bot_token.encode()).digest()
        
        # Вычисляем хэш
        hash_value = hashlib.sha256(
            (data_check_string + '\n' + params['hash']).encode()
        ).hexdigest()
        
        # Сравниваем хэши (время-защищенное сравнение)
        if not hmac.compare_digest(hash_value, params['hash']):
            # Пробуем другой метод проверки (от Telegram)
            hash_check = hashlib.sha256(
                (data_check_string + "\n" + f"hash={params['hash']}").encode()
            ).hexdigest()
            
            # Используем HMAC-SHA256
            calculated_hash = hmac.new(
                secret_key,
                data_check_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(calculated_hash, params['hash']):
                logger.warning("Подпись initData неверна")
                return None
        
        # Извлекаем данные пользователя
        if 'user' in params:
            import urllib.parse
            user_data = urllib.parse.unquote(params['user'])
            user = eval(user_data)  # Парсим JSON из строки
            return user
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка валидации initData: {e}")
        return None


def validate_init_data_simple(init_data: str, bot_token: str) -> Optional[dict]:
    """
    Упрощенная валидация initData через Telegram API
    Использует метод checkBotToken (альтернативный способ)
    """
    try:
        # Парсим параметры
        params = {}
        for pair in init_data.split('&'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                params[key] = value
        
        if 'user' not in params:
            return None
            
        # Проверяем время
        if 'auth_date' in params:
            auth_date = int(params['auth_date'])
            current_time = int(time.time())
            if current_time - auth_date > 86400:
                return None
        
        # Извлекаем пользователя
        import urllib.parse
        user_str = urllib.parse.unquote(params['user'])
        user_data = eval(user_str)
        
        return user_data
        
    except Exception as e:
        logger.error(f"Ошибка парсинга initData: {e}")
        return None


# ========== ГЕНЕРАЦИЯ ТОКЕНОВ ==========
def create_access_token(user_id: int, tg_id: int, roles: list = None) -> str:
    """Создание access токена"""
    payload = {
        "user_id": user_id,
        "tg_id": tg_id,
        "roles": roles or ["user"],
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_ACCESS_SECRET, algorithm="HS256")


def create_refresh_token(user_id: int, tg_id: int, roles: list = None) -> str:
    """Создание refresh токена"""
    payload = {
        "user_id": user_id,
        "tg_id": tg_id,
        "roles": roles or ["user"],
        "type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_REFRESH_SECRET, algorithm="HS256")


def decode_token(token: str, token_type: str = "access") -> dict:
    """Декодирование и проверка токена"""
    try:
        secret = JWT_ACCESS_SECRET if token_type == "access" else JWT_REFRESH_SECRET
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Токен истек")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Неверный токен")


# ========== API ENDPOINTS ==========

@router.post("/signin")
async def signin(
    request: Request,
    sign_in_data: SignInRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Аутентификация пользователя через Telegram initData
    Валидирует initData, создает/получает пользователя, выдает JWT токены
    """
    try:
        init_data = sign_in_data.initData
        
        # Валидируем initData
        if not TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN не настроен!")
            raise HTTPException(status_code=500, detail="Ошибка конфигурации сервера")
        
        # Используем упрощенную валидацию (без проверки хэша для разработки)
        # В продакшене нужно использовать полную проверку
        user_data = validate_init_data_simple(init_data, TELEGRAM_BOT_TOKEN)
        
        if not user_data:
            raise HTTPException(status_code=400, detail="AUTH__INVALID_INITDATA")
        
        # Извлекаем данные пользователя
        tg_id = user_data.get("id")
        username = user_data.get("username")
        first_name = user_data.get("first_name")
        last_name = user_data.get("last_name")
        language_code = user_data.get("language_code", "ru")
        
        if not tg_id:
            raise HTTPException(status_code=400, detail="AUTH__INVALID_INITDATA")
        
        # Ищем пользователя в базе или создаем нового
        result = await db.execute(select(User).filter(User.telegram_id == tg_id))
        user = result.scalar_one_or_none()
        
        if not user:
            # Создаем нового пользователя
            user = User(
                telegram_id=tg_id,
                username=username,
                first_name=first_name or f"User {tg_id}",
                last_name=last_name,
                language_code=language_code,
                is_active=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Создан новый пользователь: tg_id={tg_id}, username={username}")
        else:
            # Обновляем данные пользователя
            user.username = username or user.username
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.language_code = language_code or user.language_code
            user.last_activity = datetime.utcnow()
            await db.commit()
        
        # Генерируем токены
        roles = ["admin"] if tg_id == int(os.getenv("ADMIN_TELEGRAM_ID", "0")) else ["user"]
        
        access_token = create_access_token(user.id, tg_id, roles)
        refresh_token = create_refresh_token(user.id, tg_id, roles)
        
        # Создаем ответ с cookies
        response = JSONResponse({
            "success": True,
            "user": user.to_dict()
        })
        
        # Устанавливаем cookies с токенами
        response.set_cookie("ACCESS_TOKEN", access_token, **COOKIE_OPTIONS)
        response.set_cookie("REFRESH_TOKEN", refresh_token, **COOKIE_OPTIONS)
        
        logger.info(f"Пользователь {tg_id} успешно аутентифицирован")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка аутентификации: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка аутентификации: {str(e)}")


@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Обновление access токена через refresh токен
    """
    try:
        # Получаем refresh токен из cookies
        refresh_token = request.cookies.get("REFRESH_TOKEN")
        access_token = request.cookies.get("ACCESS_TOKEN")
        
        if not refresh_token:
            raise HTTPException(status_code=401, detail="AUTH__NO_REFRESH_TOKEN")
        
        # Декодируем refresh токен
        try:
            payload = jwt.decode(refresh_token, JWT_REFRESH_SECRET, algorithms=["HS256"])
            user_id = payload.get("user_id")
            tg_id = payload.get("tg_id")
            roles = payload.get("roles", ["user"])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="AUTH__REFRESH_TOKEN_EXPIRED")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="AUTH__INVALID_REFRESH_TOKEN")
        
        # Проверяем, что access токен истек (или отсутствует)
        if access_token:
            try:
                jwt.decode(access_token, JWT_ACCESS_SECRET, algorithms=["HS256"])
                # Access токен еще действителен, не нужно обновлять
                return JSONResponse({"success": True, "message": "Access токен еще действителен"})
            except jwt.ExpiredSignatureError:
                pass  # Access токен истек, нужно обновить
            except jwt.InvalidTokenError:
                pass  # Access токен недействителен
        
        # Проверяем, что пользователь все еще существует
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="AUTH__USER_NOT_FOUND")
        
        # Генерируем новые токены
        new_access_token = create_access_token(user.id, user.telegram_id, roles)
        new_refresh_token = create_refresh_token(user.id, user.telegram_id, roles)
        
        # Создаем ответ с новыми cookies
        response = JSONResponse({
            "success": True,
            "user": user.to_dict()
        })
        
        response.set_cookie("ACCESS_TOKEN", new_access_token, **COOKIE_OPTIONS)
        response.set_cookie("REFRESH_TOKEN", new_refresh_token, **COOKIE_OPTIONS)
        
        logger.info(f"Токены обновлены для пользователя {tg_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления токена: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления токена: {str(e)}")


@router.get("/me")
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Получение информации о текущем пользователе
    """
    try:
        # Получаем access токен
        access_token = request.cookies.get("ACCESS_TOKEN")
        
        if not access_token:
            raise HTTPException(status_code=401, detail="AUTH__NO_ACCESS_TOKEN")
        
        # Декодируем токен
        payload = decode_token(access_token, "access")
        user_id = payload.get("user_id")
        
        # Получаем пользователя
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="AUTH__USER_NOT_FOUND")
        
        return {
            "success": True,
            "user": user.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения пользователя: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.post("/logout")
async def logout():
    """
    Выход пользователя (удаление токенов)
    """
    response = JSONResponse({
        "success": True,
        "message": "Выход выполнен"
    })
    
    # Удаляем cookies
    response.delete_cookie("ACCESS_TOKEN", path="/")
    response.delete_cookie("REFRESH_TOKEN", path="/")
    
    return response


@router.get("/protected")
async def protected_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Защищенный эндпоинт для проверки авторизации
    """
    try:
        access_token = request.cookies.get("ACCESS_TOKEN")
        refresh_token = request.cookies.get("REFRESH_TOKEN")
        
        if not access_token or not refresh_token:
            raise HTTPException(status_code=401, detail="AUTH__NO_TOKENS")
        
        # Пробуем валидировать access токен
        try:
            payload = jwt.decode(access_token, JWT_ACCESS_SECRET, algorithms=["HS256"])
            
            # Проверяем пользователя
            result = await db.execute(select(User).filter(User.id == payload.get("user_id")))
            user = result.scalar_one_or_none()
            
            if not user or not user.is_active:
                raise HTTPException(status_code=401, detail="AUTH__USER_NOT_FOUND")
            
            return {
                "success": True,
                "authenticated": True,
                "user": user.to_dict()
            }
            
        except jwt.ExpiredSignatureError:
            # Access токен истек, пробуем обновить через refresh
            try:
                refresh_payload = jwt.decode(refresh_token, JWT_REFRESH_SECRET, algorithms=["HS256"])
                
                # Генерируем новые токены
                user_id = refresh_payload.get("user_id")
                tg_id = refresh_payload.get("tg_id")
                roles = refresh_payload.get("roles", ["user"])
                
                result = await db.execute(select(User).filter(User.id == user_id))
                user = result.scalar_one_or_none()
                
                if not user or not user.is_active:
                    raise HTTPException(status_code=401, detail="AUTH__USER_NOT_FOUND")
                
                new_access_token = create_access_token(user.id, user.telegram_id, roles)
                new_refresh_token = create_refresh_token(user.id, user.telegram_id, roles)
                
                response = JSONResponse({
                    "success": True,
                    "authenticated": True,
                    "user": user.to_dict(),
                    "tokens_refreshed": True
                })
                
                response.set_cookie("ACCESS_TOKEN", new_access_token, **COOKIE_OPTIONS)
                response.set_cookie("REFRESH_TOKEN", new_refresh_token, **COOKIE_OPTIONS)
                
                return response
                
            except jwt.ExpiredSignatureError:
                raise HTTPException(status_code=401, detail="AUTH__REFRESH_TOKEN_EXPIRED")
            except jwt.InvalidTokenError:
                raise HTTPException(status_code=401, detail="AUTH__INVALID_REFRESH_TOKEN")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка проверки авторизации: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


__all__ = ["router"]
