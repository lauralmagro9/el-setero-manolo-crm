"""merge the company billing NIF/CIF into the single tax_id

Revision ID: f6c1d2e3a4b5
Revises: e5b3c8a1d9f2
Create Date: 2026-11-13 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f6c1d2e3a4b5'
down_revision: Union[str, Sequence[str], None] = 'e5b3c8a1d9f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep only the fiscal NIF/CIF (tax_id), preferring the billing one that invoices used."""
    # tax_id is unique: only one company per billing value takes it, and only if it is free
    op.execute("""
        UPDATE company SET tax_id = billing_tax_id
        WHERE billing_tax_id IS NOT NULL
          AND id = (SELECT c2.id FROM company c2 WHERE c2.billing_tax_id = company.billing_tax_id
                    ORDER BY c2.id LIMIT 1)
          AND NOT EXISTS (SELECT 1 FROM company c3
                          WHERE c3.tax_id = company.billing_tax_id AND c3.id <> company.id)
    """)
    op.drop_column('company', 'billing_tax_id')


def downgrade() -> None:
    """Restore the billing_tax_id column, filled with the tax_id."""
    op.add_column('company', sa.Column('billing_tax_id', sa.String(length=30), nullable=True))
    op.execute("UPDATE company SET billing_tax_id = tax_id")
