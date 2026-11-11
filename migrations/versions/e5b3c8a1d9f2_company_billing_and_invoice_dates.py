"""company billing data, invoice operation date; invoices are linked to a company only

Revision ID: e5b3c8a1d9f2
Revises: d7a2b9c3f1e5
Create Date: 2026-11-12 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5b3c8a1d9f2'
down_revision: Union[str, Sequence[str], None] = 'd7a2b9c3f1e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Billing fields on the company; operation date on the invoice; drop contact, email and phone."""
    op.alter_column('company', 'legal_name', new_column_name='billing_name')
    op.add_column('company', sa.Column('billing_address', sa.String(length=300), nullable=True))
    op.add_column('company', sa.Column('billing_tax_id', sa.String(length=30), nullable=True))

    op.add_column('invoice', sa.Column('operation_date', sa.Date(), nullable=True))
    op.execute("UPDATE invoice SET operation_date = issue_date")
    op.drop_constraint('fk_invoice_contact', 'invoice', type_='foreignkey')
    op.drop_column('invoice', 'contact_id')
    op.drop_column('invoice', 'customer_email')
    op.drop_column('invoice', 'customer_phone')


def downgrade() -> None:
    """Restore the previous columns (their data is lost)."""
    op.add_column('invoice', sa.Column('customer_phone', sa.String(length=20), nullable=True))
    op.add_column('invoice', sa.Column('customer_email', sa.String(length=200), nullable=True))
    op.add_column('invoice', sa.Column('contact_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_invoice_contact', 'invoice', 'contact', ['contact_id'], ['id'])
    op.drop_column('invoice', 'operation_date')

    op.drop_column('company', 'billing_tax_id')
    op.drop_column('company', 'billing_address')
    op.alter_column('company', 'billing_name', new_column_name='legal_name')
