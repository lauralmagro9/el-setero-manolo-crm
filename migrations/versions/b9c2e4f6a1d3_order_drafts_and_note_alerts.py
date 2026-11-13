"""order drafts and the "nota_procesada" / "pedido_incompleto" alert types

Revision ID: b9c2e4f6a1d3
Revises: a8e4d1c7b2f9
Create Date: 2026-11-13 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from crm import enums as e
from crm.security import secure_public_schema
from crm.utils import enum_column


# revision identifiers, used by Alembic.
revision: str = 'b9c2e4f6a1d3'
down_revision: Union[str, Sequence[str], None] = 'a8e4d1c7b2f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT = 'ck_alerttype'
NEW_TYPES = (e.AlertType.NOTE_PROCESSED, e.AlertType.INCOMPLETE_ORDER)


def _alert_type_check(values: list[str]) -> str:
    """Return the CHECK expression restricting alert.type to `values`."""
    quoted = ", ".join("'" + v + "'" for v in values)
    return f"type IN ({quoted})"


def upgrade() -> None:
    """Allow the new alert types and create the order_draft table."""
    op.drop_constraint(CONSTRAINT, 'alert', type_='check')
    op.create_check_constraint(CONSTRAINT, 'alert', _alert_type_check([t.value for t in e.AlertType]))
    op.create_table(
        'order_draft',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('interaction_id', sa.Uuid(), nullable=True),
        sa.Column('company_id', sa.Uuid(), nullable=True),
        sa.Column('contact_id', sa.Uuid(), nullable=True),
        sa.Column('requested_delivery_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('items', sa.JSON(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', enum_column(e.OrderDraftStatus), nullable=False),
        sa.Column('order_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['interaction_id'], ['interaction.id']),
        sa.ForeignKeyConstraint(['company_id'], ['company.id']),
        sa.ForeignKeyConstraint(['contact_id'], ['contact.id']),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_order_draft_interaction_id'), 'order_draft', ['interaction_id'], unique=False)
    op.create_index(op.f('ix_order_draft_status'), 'order_draft', ['status'], unique=False)
    secure_public_schema(op.get_bind())


def downgrade() -> None:
    """Drop the order_draft table and restore the previous alert types."""
    op.drop_table('order_draft')
    removed = ", ".join("'" + t.value + "'" for t in NEW_TYPES)
    op.execute(f"DELETE FROM alert WHERE type IN ({removed})")
    op.drop_constraint(CONSTRAINT, 'alert', type_='check')
    op.create_check_constraint(
        CONSTRAINT, 'alert', _alert_type_check([t.value for t in e.AlertType if t not in NEW_TYPES]),
    )
