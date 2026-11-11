"""manual invoices: optional order, customer snapshot, series numbering and email status

Revision ID: d7a2b9c3f1e5
Revises: c4d8e1f0a2b6
Create Date: 2026-11-11 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from crm import enums as e
from crm.security import secure_public_schema
from crm.utils import enum_column
from crm.views import INVOICE_BALANCE


# revision identifiers, used by Alembic.
revision: str = 'd7a2b9c3f1e5'
down_revision: Union[str, Sequence[str], None] = 'c4d8e1f0a2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_CUSTOMER_NAME = (
    "COALESCE(i.customer_name, (SELECT c.name FROM orders o JOIN company c ON c.id = o.company_id\n"
    "          WHERE o.id = i.order_id)) AS customer_name,"
)
OLD_CUSTOMER_NAME = (
    "(SELECT c.name FROM orders o JOIN company c ON c.id = o.company_id\n"
    "          WHERE o.id = i.order_id) AS customer_name,"
)


def upgrade() -> None:
    """Allow invoices without order and store everything a manual invoice needs."""
    op.execute("DROP VIEW IF EXISTS invoice_balance")

    op.add_column('company', sa.Column('legal_name', sa.String(length=200), nullable=True))

    op.alter_column('invoice', 'order_id', nullable=True)
    op.add_column('invoice', sa.Column('company_id', sa.Uuid(), nullable=True))
    op.add_column('invoice', sa.Column('contact_id', sa.Uuid(), nullable=True))
    op.add_column('invoice', sa.Column('invoice_type', enum_column(e.InvoiceType), nullable=False, server_default='VDA'))
    op.add_column('invoice', sa.Column('fiscal_year', sa.Integer(), nullable=True))
    op.add_column('invoice', sa.Column('sequence_number', sa.Integer(), nullable=True))
    op.add_column('invoice', sa.Column('customer_name', sa.String(length=200), nullable=True))
    op.add_column('invoice', sa.Column('customer_tax_id', sa.String(length=30), nullable=True))
    op.add_column('invoice', sa.Column('customer_address', sa.String(length=300), nullable=True))
    op.add_column('invoice', sa.Column('customer_email', sa.String(length=200), nullable=True))
    op.add_column('invoice', sa.Column('customer_phone', sa.String(length=20), nullable=True))
    op.add_column('invoice', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('invoice', sa.Column('email_status', enum_column(e.EmailStatus), nullable=False, server_default='pending'))
    op.add_column('invoice', sa.Column('email_recipient', sa.String(length=200), nullable=True))
    op.add_column('invoice', sa.Column('email_sent_at', sa.DateTime(), nullable=True))
    op.add_column('invoice', sa.Column('email_error', sa.Text(), nullable=True))
    op.add_column('invoice', sa.Column('created_by', sa.String(length=100), nullable=True))
    op.add_column('invoice', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_invoice_company_id'), 'invoice', ['company_id'], unique=False)
    op.create_foreign_key('fk_invoice_company', 'invoice', 'company', ['company_id'], ['id'])
    op.create_foreign_key('fk_invoice_contact', 'invoice', 'contact', ['contact_id'], ['id'])
    op.create_unique_constraint('uq_invoice_series_number', 'invoice', ['invoice_type', 'fiscal_year', 'sequence_number'])

    op.add_column('invoice_item', sa.Column('product_id', sa.Uuid(), nullable=True))
    op.add_column('invoice_item', sa.Column('position', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('invoice_item', sa.Column('product_name', sa.String(length=200), nullable=True))
    op.create_foreign_key('fk_invoice_item_product', 'invoice_item', 'product', ['product_id'], ['id'])

    op.create_table(
        'invoice_counter',
        sa.Column('invoice_type', enum_column(e.InvoiceType), nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('last_number', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('invoice_type', 'fiscal_year'),
    )

    # invoice_balance is created by `f6c1d2a8b3e7` (the current definition needs its soft-delete columns)
    secure_public_schema(op.get_bind())


def downgrade() -> None:
    """Remove the manual-invoice columns (manual invoices without order must be deleted first)."""
    op.execute("DROP VIEW IF EXISTS invoice_balance")
    op.drop_table('invoice_counter')
    op.drop_constraint('fk_invoice_item_product', 'invoice_item', type_='foreignkey')
    op.drop_column('invoice_item', 'product_name')
    op.drop_column('invoice_item', 'position')
    op.drop_column('invoice_item', 'product_id')
    op.drop_constraint('uq_invoice_series_number', 'invoice', type_='unique')
    op.drop_constraint('fk_invoice_contact', 'invoice', type_='foreignkey')
    op.drop_constraint('fk_invoice_company', 'invoice', type_='foreignkey')
    op.drop_index(op.f('ix_invoice_company_id'), table_name='invoice')
    for column in ('created_at', 'created_by', 'email_error', 'email_sent_at', 'email_recipient',
                   'email_status', 'notes', 'customer_phone', 'customer_email', 'customer_address',
                   'customer_tax_id', 'customer_name', 'sequence_number', 'fiscal_year',
                   'invoice_type', 'contact_id', 'company_id'):
        op.drop_column('invoice', column)
    op.alter_column('invoice', 'order_id', nullable=False)
    op.drop_column('company', 'legal_name')
    op.execute(INVOICE_BALANCE.replace(NEW_CUSTOMER_NAME, OLD_CUSTOMER_NAME))
