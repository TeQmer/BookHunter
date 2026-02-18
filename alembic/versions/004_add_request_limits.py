#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Добавление полей для отслеживания лимитов запросов
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers
revision = '004_add_request_limits'
down_revision = '003_add_publisher_and_binding'
branch_labels = None
depends_on = None


def upgrade():
    """Добавляем поля для отслеживания лимитов запросов"""
    op.add_column('users', sa.Column('daily_requests_used', sa.Integer(), server_default='0', nullable=True))
    op.add_column('users', sa.Column('daily_requests_limit', sa.Integer(), server_default='15', nullable=True))
    op.add_column('users', sa.Column('requests_updated_at', sa.DateTime(), nullable=True))

    # Обновляем существующие записи
    op.execute("""
        UPDATE users
        SET daily_requests_used = 0,
            daily_requests_limit = 15,
            requests_updated_at = CURRENT_TIMESTAMP
        WHERE daily_requests_used IS NULL
    """)

    # Делаем поля NOT NULL после заполнения
    op.alter_column('users', 'daily_requests_used', nullable=False)
    op.alter_column('users', 'daily_requests_limit', nullable=False)


def downgrade():
    """Удаляем поля для отслеживания лимитов запросов"""
    op.drop_column('users', 'requests_updated_at')
    op.drop_column('users', 'daily_requests_limit')
    op.drop_column('users', 'daily_requests_used')
