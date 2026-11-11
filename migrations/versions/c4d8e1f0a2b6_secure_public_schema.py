"""secure the public schema: RLS on every table, no access for the Supabase API roles

Revision ID: c4d8e1f0a2b6
Revises: a1f3c9d2e7b4
Create Date: 2026-11-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

from crm.security import secure_public_schema, unsecure_public_schema


# revision identifiers, used by Alembic.
revision: str = 'c4d8e1f0a2b6'
down_revision: Union[str, Sequence[str], None] = 'a1f3c9d2e7b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Close the REST API of Supabase to the data: only the backend may read or write."""
    secure_public_schema(op.get_bind())


def downgrade() -> None:
    """Restore Supabase's default open permissions."""
    unsecure_public_schema(op.get_bind())
