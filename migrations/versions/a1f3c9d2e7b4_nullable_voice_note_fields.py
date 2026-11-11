"""interaction: company and summary become optional (voice notes)

Revision ID: a1f3c9d2e7b4
Revises: 5b0627280188
Create Date: 2026-11-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1f3c9d2e7b4'
down_revision: Union[str, Sequence[str], None] = '5b0627280188'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow voice notes without company and without summary."""
    op.alter_column('interaction', 'company_id', nullable=True)
    op.alter_column('interaction', 'summary', nullable=True)


def downgrade() -> None:
    """Restore the NOT NULL constraints (unassigned notes must be fixed first)."""
    op.execute("UPDATE interaction SET summary = COALESCE(summary, transcript, '')")
    op.alter_column('interaction', 'summary', nullable=False)
    op.alter_column('interaction', 'company_id', nullable=False)
