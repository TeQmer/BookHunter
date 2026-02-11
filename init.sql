-- Создание базы данных для системы мониторинга скидок
CREATE DATABASE book_discounts;

-- Подключение к базе данных
\c book_discounts;

-- Установка расширений
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Создание схемы для приложения
CREATE SCHEMA IF NOT EXISTS app;

-- Настройка часового пояса
SET timezone = 'Europe/Moscow';
