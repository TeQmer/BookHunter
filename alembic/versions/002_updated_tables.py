"""Create updated tables with new models

Revision ID: 002_updated_tables
Revises: 001_initial_tables
Create Date: 2026-02-03 03:45:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_updated_tables'
down_revision = '001_initial_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Удаляем старые таблицы если они существуют
    try:
        op.drop_table('notifications')
    except Exception:
        pass
    
    try:
        op.drop_table('alerts')
    except Exception:
        pass
    
    try:
        op.drop_table('books')
    except Exception:
        pass
    
    try:
        op.drop_table('users')
    except Exception:
        pass
    
    try:
        op.drop_table('parsing_logs')
    except Exception:
        pass

    # Создание обновленной таблицы users
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=255), nullable=False),
        sa.Column('last_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('language_code', sa.String(length=10), default='ru'),
        sa.Column('timezone', sa.String(length=50), default='Europe/Moscow'),
        sa.Column('total_alerts', sa.Integer(), default=0),
        sa.Column('notifications_sent', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)

    # Создание обновленной таблицы books
    op.create_table('books',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('publisher', sa.String(length=255), nullable=True),
        sa.Column('isbn', sa.String(length=20), nullable=True),
        sa.Column('current_price', sa.Float(), nullable=False),
        sa.Column('old_price', sa.Float(), nullable=True),
        sa.Column('discount_percent', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=10), default='RUB'),
        sa.Column('product_url', sa.String(length=1000), nullable=False),
        sa.Column('image_url', sa.String(length=1000), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('source_id', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('pages', sa.Integer(), nullable=True),
        sa.Column('format_size', sa.String(length=50), nullable=True),
        sa.Column('is_available', sa.Boolean(), default=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('reviews_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.Column('last_checked', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_books_id'), 'books', ['id'], unique=False)
    op.create_index(op.f('ix_books_title'), 'books', ['title'], unique=False)
    op.create_index(op.f('ix_books_author'), 'books', ['author'], unique=False)
    op.create_index(op.f('ix_books_source'), 'books', ['source'], unique=False)
    op.create_index(op.f('ix_books_title_author'), 'books', ['title', 'author'], unique=False)
    op.create_index(op.f('ix_books_source_price'), 'books', ['source', 'current_price'], unique=False)
    op.create_index(op.f('ix_books_discount'), 'books', ['discount_percent'], unique=False)
    op.create_index(op.f('ix_books_available'), 'books', ['is_available', 'is_active'], unique=False)
    op.create_index(op.f('ix_books_updated'), 'books', ['updated_at'], unique=False)

    # Создание обновленной таблицы alerts
    op.create_table('alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=True),
        sa.Column('book_title', sa.String(length=500), nullable=False),
        sa.Column('book_author', sa.String(length=255), nullable=True),
        sa.Column('book_source', sa.String(length=50), nullable=False),
        sa.Column('target_price', sa.Float(), nullable=True),
        sa.Column('target_discount', sa.Float(), nullable=True),
        sa.Column('min_discount', sa.Float(), nullable=True),
        sa.Column('max_price', sa.Float(), nullable=True),
        sa.Column('author_filter', sa.String(length=255), nullable=True),
        sa.Column('publisher_filter', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('notification_type', sa.String(length=50), default='price_drop'),
        sa.Column('matches_found', sa.Integer(), default=0),
        sa.Column('notifications_sent', sa.Integer(), default=0),
        sa.Column('last_notification', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('search_query', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['book_id'], ['books.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_id'), 'alerts', ['id'], unique=False)
    op.create_index(op.f('ix_alerts_user_active'), 'alerts', ['user_id', 'is_active'], unique=False)
    op.create_index(op.f('ix_alerts_source'), 'alerts', ['book_source'], unique=False)
    op.create_index(op.f('ix_alerts_price'), 'alerts', ['target_price'], unique=False)
    op.create_index(op.f('ix_alerts_discount'), 'alerts', ['target_discount'], unique=False)
    op.create_index(op.f('ix_alerts_expires'), 'alerts', ['expires_at'], unique=False)

    # Создание обновленной таблицы notifications
    op.create_table('notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=True),
        sa.Column('book_title', sa.String(length=500), nullable=False),
        sa.Column('book_author', sa.String(length=255), nullable=True),
        sa.Column('book_price', sa.String(length=50), nullable=True),
        sa.Column('book_discount', sa.String(length=20), nullable=True),
        sa.Column('book_url', sa.String(length=1000), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('message_type', sa.String(length=50), default='text'),
        sa.Column('channel', sa.String(length=50), default='telegram'),
        sa.Column('telegram_message_id', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), default='pending'),
        sa.Column('is_sent', sa.Boolean(), default=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), default=0),
        sa.Column('max_retries', sa.Integer(), default=3),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_id'), 'notifications', ['id'], unique=False)
    op.create_index(op.f('ix_notifications_user'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_notifications_alert'), 'notifications', ['alert_id'], unique=False)
    op.create_index(op.f('ix_notifications_status'), 'notifications', ['status'], unique=False)
    op.create_index(op.f('ix_notifications_sent'), 'notifications', ['is_sent', 'sent_at'], unique=False)
    op.create_index(op.f('ix_notifications_scheduled'), 'notifications', ['scheduled_for'], unique=False)
    op.create_index(op.f('ix_notifications_created'), 'notifications', ['created_at'], unique=False)

    # Создание обновленной таблицы parsing_logs
    op.create_table('parsing_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('task_type', sa.String(length=50), default='discount_check'),
        sa.Column('status', sa.String(length=50), default='running'),
        sa.Column('is_success', sa.Boolean(), default=False),
        sa.Column('pages_parsed', sa.Integer(), default=0),
        sa.Column('books_found', sa.Integer(), default=0),
        sa.Column('books_updated', sa.Integer(), default=0),
        sa.Column('books_added', sa.Integer(), default=0),
        sa.Column('books_removed', sa.Integer(), default=0),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('warning_message', sa.Text(), nullable=True),
        sa.Column('request_count', sa.Integer(), default=0),
        sa.Column('successful_requests', sa.Integer(), default=0),
        sa.Column('failed_requests', sa.Integer(), default=0),
        sa.Column('search_query', sa.String(length=500), nullable=True),
        sa.Column('max_pages', sa.Integer(), nullable=True),
        sa.Column('rate_limit_delay', sa.Float(), default=2.0),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('proxy_used', sa.String(length=100), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_parsing_logs_id'), 'parsing_logs', ['id'], unique=False)
    op.create_index(op.f('ix_parsing_logs_source_status'), 'parsing_logs', ['source', 'status'], unique=False)
    op.create_index(op.f('ix_parsing_logs_started'), 'parsing_logs', ['started_at'], unique=False)
    op.create_index(op.f('ix_parsing_logs_success'), 'parsing_logs', ['is_success'], unique=False)
    op.create_index(op.f('ix_parsing_logs_duration'), 'parsing_logs', ['duration_seconds'], unique=False)
    op.create_index(op.f('ix_parsing_logs_books_found'), 'parsing_logs', ['books_found'], unique=False)


def downgrade() -> None:
    # Удаляем индексы в обратном порядке
    op.drop_index(op.f('ix_parsing_logs_books_found'), table_name='parsing_logs')
    op.drop_index(op.f('ix_parsing_logs_duration'), table_name='parsing_logs')
    op.drop_index(op.f('ix_parsing_logs_success'), table_name='parsing_logs')
    op.drop_index(op.f('ix_parsing_logs_started'), table_name='parsing_logs')
    op.drop_index(op.f('ix_parsing_logs_source_status'), table_name='parsing_logs')
    op.drop_index(op.f('ix_parsing_logs_id'), table_name='parsing_logs')
    op.drop_table('parsing_logs')
    
    op.drop_index(op.f('ix_notifications_created'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_scheduled'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_sent'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_status'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_alert'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_user'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_id'), table_name='notifications')
    op.drop_table('notifications')
    
    op.drop_index(op.f('ix_alerts_expires'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_discount'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_price'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_source'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_user_active'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_id'), table_name='alerts')
    op.drop_table('alerts')
    
    op.drop_index(op.f('ix_books_updated'), table_name='books')
    op.drop_index(op.f('ix_books_available'), table_name='books')
    op.drop_index(op.f('ix_books_discount'), table_name='books')
    op.drop_index(op.f('ix_books_source_price'), table_name='books')
    op.drop_index(op.f('ix_books_title_author'), table_name='books')
    op.drop_index(op.f('ix_books_source'), table_name='books')
    op.drop_index(op.f('ix_books_author'), table_name='books')
    op.drop_index(op.f('ix_books_title'), table_name='books')
    op.drop_index(op.f('ix_books_id'), table_name='books')
    op.drop_table('books')
    
    op.drop_index(op.f('ix_users_telegram_id'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
