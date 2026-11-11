"""Vistas SQL con todos los valores calculados del modelo (una sola fuente de la verdad).

SQL estándar, válido en SQLite y PostgreSQL. El orden importa: unas vistas usan otras.
Si cambias una vista, crea una migración nueva que la elimine y la vuelva a crear.
Todas excluyen los registros borrados (deleted_at no nulo): es el borrado lógico.
"""

from sqlalchemy import Connection, text

# --- Stock por lote: recibido - reservado - consumido - ajustes ----------------------------
LOT_STOCK = """
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
          WHERE a.lot_id = l.id AND a.deleted_at IS NULL AND a.status = 'reservada') AS reserved_quantity,
        (SELECT COALESCE(SUM(a.quantity), 0) FROM lot_allocation a
          WHERE a.lot_id = l.id AND a.deleted_at IS NULL AND a.status = 'consumida') AS consumed_quantity,
        (SELECT COALESCE(SUM(j.quantity), 0) FROM lot_adjustment j
          WHERE j.lot_id = l.id AND j.deleted_at IS NULL) AS adjusted_quantity,
        l.quantity_received
          - (SELECT COALESCE(SUM(a.quantity), 0) FROM lot_allocation a
              WHERE a.lot_id = l.id AND a.deleted_at IS NULL AND a.status IN ('reservada', 'consumida'))
          - (SELECT COALESCE(SUM(j.quantity), 0) FROM lot_adjustment j
              WHERE j.lot_id = l.id AND j.deleted_at IS NULL) AS available_quantity,
        l.additional_costs / l.quantity_received AS additional_costs_per_unit,
        l.purchase_cost_per_unit + l.additional_costs / l.quantity_received AS total_cost_per_unit,
        l.purchase_cost_per_unit * l.quantity_received + l.additional_costs AS total_cost
    FROM lot l
    WHERE l.deleted_at IS NULL
) s
"""

# --- Precio y margen por línea de pedido ---------------------------------------------------
ORDER_ITEM_PRICING = """
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
        WHERE a.status <> 'liberada' AND a.deleted_at IS NULL
        GROUP BY a.order_item_id
    ) al ON al.order_item_id = oi.id
    WHERE oi.deleted_at IS NULL AND o.deleted_at IS NULL
) p
"""

# --- Total, cobrado, pendiente y estado real de cada factura -------------------------------
INVOICE_BALANCE = """
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
          WHERE t.invoice_id = i.id AND t.deleted_at IS NULL) AS total_before_tax,
        (SELECT ROUND(COALESCE(SUM(t.quantity * t.unit_price * (1 + t.tax_rate)), 0), 2) FROM invoice_item t
          WHERE t.invoice_id = i.id AND t.deleted_at IS NULL) AS total_amount,
        (SELECT ROUND(COALESCE(SUM(y.amount), 0), 2) FROM payment y
          WHERE y.invoice_id = i.id AND y.deleted_at IS NULL) AS paid_amount
    FROM invoice i
    WHERE i.deleted_at IS NULL
) b
"""

VIEWS: dict[str, str] = {
    "lot_stock": LOT_STOCK,
    "order_item_pricing": ORDER_ITEM_PRICING,
    "invoice_balance": INVOICE_BALANCE,
}


def create_views(conn: Connection) -> None:
    """Create all views, in dependency order."""
    for sql in VIEWS.values():
        conn.execute(text(sql))


def drop_views(conn: Connection) -> None:
    """Drop all views, in reverse dependency order."""
    for name in reversed(VIEWS):
        conn.execute(text(f"DROP VIEW IF EXISTS {name}"))
