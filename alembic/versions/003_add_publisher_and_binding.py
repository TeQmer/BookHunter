"""Add publisher and binding fields to books table

Revision ID: 003_add_publisher_and_binding
Revises: 002_updated_tables
Create Date: 2026-02-04 12:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_add_publisher_and_binding'
down_revision = '002_updated_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле publisher (издательство)
    op.add_column('books', sa.Column('publisher', sa.String(length=255), nullable=True))

    # Добавляем поле binding (переплёт)
    op.add_column('books', sa.Column('binding', sa.String(length=100), nullable=True))

    # Создаем индексы для оптимизации поиска
    op.create_index('ix_books_publisher', 'books', ['publisher'])
    op.create_index('ix_books_binding', 'books', ['binding'])


def downgrade() -> None:
    # Удаляем индексы
    op.drop_index('ix_books_binding', table_name='books')
    op.drop_index('ix_books_publisher', table_name='books')

    # Удаляем столбцы
    op.drop_column('books', 'binding')
    op.drop_column('books', 'publisher')
