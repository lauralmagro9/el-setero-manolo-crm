"""alerts raised by the agents and product aliases

Revision ID: a8e4d1c7b2f9
Revises: f6c1d2a8b3e7
Create Date: 2026-11-12 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from crm import enums as e
from crm.security import secure_public_schema
from crm.utils import enum_column


# revision identifiers, used by Alembic.
revision: str = 'a8e4d1c7b2f9'
down_revision: Union[str, Sequence[str], None] = 'f6c1d2a8b3e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the alert table and add the aliases column to product."""
    op.add_column('product', sa.Column('aliases', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.create_table(
        'alert',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('type', enum_column(e.AlertType), nullable=False),
        sa.Column('severity', enum_column(e.AlertSeverity), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=True),
        sa.Column('lot_id', sa.Uuid(), nullable=True),
        sa.Column('company_id', sa.Uuid(), nullable=True),
        sa.Column('order_id', sa.Uuid(), nullable=True),
        sa.Column('interaction_id', sa.Uuid(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('dedupe_key', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['product.id']),
        sa.ForeignKeyConstraint(['lot_id'], ['lot.id']),
        sa.ForeignKeyConstraint(['company_id'], ['company.id']),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['interaction_id'], ['interaction.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_alert_type'), 'alert', ['type'], unique=False)
    op.create_index(op.f('ix_alert_read_at'), 'alert', ['read_at'], unique=False)
    op.create_index('uq_alert_dedupe_key', 'alert', ['dedupe_key'], unique=True,
                    postgresql_where=sa.text('deleted_at IS NULL'))
    secure_public_schema(op.get_bind())


def downgrade() -> None:
    """Drop the alert table and the aliases column."""
    op.drop_table('alert')
    op.drop_column('product', 'aliases')
