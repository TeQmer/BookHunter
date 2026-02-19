#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Изменение типа поля telegram_id на BigInteger для поддержки больших ID
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '005_change_telegram_id_to_bigint'
down_revision = '004_add_request_limits'
branch_labels = None
depends_on = None


def upgrade():
    """Изменяем тип telegram_id на BigInteger"""
    # Сначала изменяем тип на bigint
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN telegram_id TYPE BIGINT
    """)


def downgrade():
    """Возвращаем тип обратно на Integer"""
    # Возвращаем тип на integer
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN telegram_id TYPE INTEGER
    """)
