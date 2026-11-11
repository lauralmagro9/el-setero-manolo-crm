"""audit columns (created_at, modified_at, created_by), soft delete and gender-neutral customer statuses

Revision ID: f6c1d2a8b3e7
Revises: f6c1d2e3a4b5
Create Date: 2026-11-12 12:00:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from crm.security import secure_public_schema
from crm.views import create_views, drop_views


# revision identifiers, used by Alembic.
revision: str = 'f6c1d2a8b3e7'
down_revision: Union[str, Sequence[str], None] = 'f6c1d2e3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    'company', 'contact', 'interaction', 'product', 'lot', 'lot_adjustment', 'orders', 'order_item',
    'lot_allocation', 'invoice', 'invoice_counter', 'invoice_item', 'payment', 'agent_execution',
]
# Columns each table gets: (name, type, mandatory)
COLUMNS = [
    ('created_at', sa.DateTime(), True),
    ('modified_at', sa.DateTime(), True),
    ('created_by', sa.String(length=100), True),
    ('deleted_at', sa.DateTime(), False),
    ('deleted_by', sa.String(length=100), False),
]
# Columns that already existed (as optional) before this migration: they are kept on downgrade
PREEXISTING = {('interaction', 'created_by'), ('invoice', 'created_by'), ('invoice', 'created_at')}
# Unique constraints that become partial unique indexes (deleted rows no longer count)
UNIQUES = [
    ('company', 'company_tax_id_key', 'uq_company_tax_id', ['tax_id']),
    ('product', 'product_name_key', 'uq_product_name', ['name']),
    ('lot', 'lot_lot_code_key', 'uq_lot_lot_code', ['lot_code']),
    ('interaction', 'interaction_source_external_id_key', 'uq_interaction_source_external_id', ['source', 'external_id']),
]
LEGACY_ACTOR = 'system'

# Customer statuses become gender-neutral (the stored text changes, the CHECK constraint with it)
STATUS_RENAMES = {
    'Contactada': 'Contactado',
    'Nada interesada': 'Nada interesado',
    'Poco interesada': 'Poco interesado',
    'Interesada': 'Interesado',
    'Muy interesada': 'Muy interesado',
}
OTHER_STATUSES = ['Cliente', 'Perdido']


def _rename_customer_statuses(mapping: dict[str, str]) -> None:
    """Rewrite company.customer_status with `mapping` and recreate its CHECK for the resulting values."""
    op.execute('ALTER TABLE company DROP CONSTRAINT IF EXISTS ck_customerstatus')
    cases = ' '.join(f"WHEN '{old}' THEN '{new}'" for old, new in mapping.items())
    op.execute(f'UPDATE company SET customer_status = CASE customer_status {cases} ELSE customer_status END')
    allowed = ', '.join(f"'{v}'" for v in [*mapping.values(), *OTHER_STATUSES])
    op.execute(f'ALTER TABLE company ADD CONSTRAINT ck_customerstatus CHECK (customer_status IN ({allowed}))')


def upgrade() -> None:
    """Add the audit and soft-delete columns, make deleted rows not count for uniqueness, redo the views."""
    bind = op.get_bind()
    drop_views(bind)
    inspector = sa.inspect(bind)
    now = datetime.now()

    for table in TABLES:
        existing = {c['name'] for c in inspector.get_columns(table)}
        for name, type_, _ in COLUMNS:
            if name not in existing:
                op.add_column(table, sa.Column(name, type_, nullable=True))
        # Rows that already exist get the migration time and the legacy actor
        op.execute(
            sa.text(
                f"UPDATE {table} SET created_at = COALESCE(created_at, :now), "
                f"modified_at = COALESCE(modified_at, created_at, :now), "
                f"created_by = COALESCE(created_by, :actor)"
            ).bindparams(now=now, actor=LEGACY_ACTOR)
        )
        for name, type_, mandatory in COLUMNS:
            if mandatory:
                op.alter_column(table, name, existing_type=type_, nullable=False)

    for table, old_name, index_name, columns in UNIQUES:
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {old_name}')
        op.create_index(index_name, table, columns, unique=True, postgresql_where=sa.text('deleted_at IS NULL'))

    _rename_customer_statuses(STATUS_RENAMES)

    create_views(bind)
    secure_public_schema(bind)


def downgrade() -> None:
    """Remove the soft-delete columns (rows that were deleted come back to life) and restore the old statuses."""
    bind = op.get_bind()
    drop_views(bind)
    _rename_customer_statuses({new: old for old, new in STATUS_RENAMES.items()})
    for table, old_name, index_name, columns in UNIQUES:
        op.drop_index(index_name, table_name=table)
        op.create_unique_constraint(old_name, table, columns)
    for table in TABLES:
        for name, type_, mandatory in COLUMNS:
            if (table, name) in PREEXISTING:
                op.alter_column(table, name, existing_type=type_, nullable=True)
            else:
                op.drop_column(table, name)
    for sql in OLD_VIEWS:
        op.execute(sql)


# The views as they were before this migration (without the deleted_at filters)
OLD_VIEWS = [
    """
CREATE VIEW lot_stock AS
SELECT
    s.*,
    CASE
        WHEN s.is_blocked THEN 'bloqueado'
        WHEN s.expiry_date IS NOT NULL AND s.expiry_date < CURRENT_DATE THEN 'caducado'
        WHEN s.available_quantity > 0 THEN 'disponible'
        WHEN s.reserved_quantity > 0 THEN 'reservado'
        ELSE 'agotado'
    END AS status
FROM (
    SELECT
        l.id AS lot_id,
        l.product_id,
        (SELECT pr.name FROM product pr WHERE pr.id = l.product_id) AS product_name,
        l.lot_code,
        l.expiry_date,
        l.is_blocked,
        l.quantity_received,
        (SELECT COALESCE(SUM(a.quantity), 0) FROM lot_allocation a
          WHERE a.lot_id = l.id AND a.status = 'reservada') AS reserved_quantity,
        (SELECT COALESCE(SUM(a.quantity), 0) FROM lot_allocation a
          WHERE a.lot_id = l.id AND a.status = 'consumida') AS consumed_quantity,
        (SELECT COALESCE(SUM(j.quantity), 0) FROM lot_adjustment j
          WHERE j.lot_id = l.id) AS adjusted_quantity,
        l.quantity_received
          - (SELECT COALESCE(SUM(a.quantity), 0) FROM lot_allocation a
              WHERE a.lot_id = l.id AND a.status IN ('reservada', 'consumida'))
          - (SELECT COALESCE(SUM(j.quantity), 0) FROM lot_adjustment j
              WHERE j.lot_id = l.id) AS available_quantity,
        l.additional_costs / l.quantity_received AS additional_costs_per_unit,
        l.purchase_cost_per_unit + l.additional_costs / l.quantity_received AS total_cost_per_unit,
        l.purchase_cost_per_unit * l.quantity_received + l.additional_costs AS total_cost
    FROM lot l
) s
""",
    """
CREATE VIEW order_item_pricing AS
SELECT
    p.*,
    p.avg_cost_per_unit / (1 - p.target_net_margin) AS suggested_unit_price_before_tax,
    p.avg_cost_per_unit / (1 - p.target_net_margin) * (1 + p.tax_rate) AS suggested_unit_price_after_tax,
    p.agreed_unit_price_after_tax / (1 + p.tax_rate) AS agreed_unit_price_before_tax,
    (p.agreed_unit_price_after_tax / (1 + p.tax_rate) - p.avg_cost_per_unit)
        / NULLIF(p.agreed_unit_price_after_tax / (1 + p.tax_rate), 0) AS final_margin
FROM (
    SELECT
        oi.id AS order_item_id,
        oi.order_id,
        oi.product_id,
        pr.name AS product_name,
        c.name AS customer_name,
        o.requested_delivery_date,
        oi.quantity,
        oi.agreed_unit_price_after_tax,
        pr.tax_rate,
        pr.target_net_margin,
        al.allocated_quantity,
        al.avg_cost_per_unit
    FROM order_item oi
    JOIN product pr ON pr.id = oi.product_id
    JOIN orders o ON o.id = oi.order_id
    JOIN company c ON c.id = o.company_id
    LEFT JOIN (
        SELECT a.order_item_id,
               SUM(a.quantity) AS allocated_quantity,
               SUM(a.quantity * ls.total_cost_per_unit) / SUM(a.quantity) AS avg_cost_per_unit
        FROM lot_allocation a
        JOIN lot_stock ls ON ls.lot_id = a.lot_id
        WHERE a.status <> 'liberada'
        GROUP BY a.order_item_id
    ) al ON al.order_item_id = oi.id
) p
""",
    """
CREATE VIEW invoice_balance AS
SELECT
    b.*,
    ROUND(b.total_amount - b.paid_amount, 2) AS outstanding_amount,
    CASE
        WHEN b.stored_status IN ('borrador', 'anulada') THEN b.stored_status
        WHEN b.paid_amount >= b.total_amount THEN 'pagada'
        WHEN b.due_date IS NOT NULL AND b.due_date < CURRENT_DATE THEN 'vencida'
        ELSE 'emitida'
    END AS status
FROM (
    SELECT
        i.id AS invoice_id,
        i.order_id,
        COALESCE(i.customer_name, (SELECT c.name FROM orders o JOIN company c ON c.id = o.company_id
          WHERE o.id = i.order_id)) AS customer_name,
        i.invoice_number,
        i.issue_date,
        i.due_date,
        i.status AS stored_status,
        (SELECT ROUND(COALESCE(SUM(t.quantity * t.unit_price), 0), 2) FROM invoice_item t
          WHERE t.invoice_id = i.id) AS total_before_tax,
        (SELECT ROUND(COALESCE(SUM(t.quantity * t.unit_price * (1 + t.tax_rate)), 0), 2) FROM invoice_item t
          WHERE t.invoice_id = i.id) AS total_amount,
        (SELECT ROUND(COALESCE(SUM(y.amount), 0), 2) FROM payment y
          WHERE y.invoice_id = i.id) AS paid_amount
    FROM invoice i
) b
""",
]
