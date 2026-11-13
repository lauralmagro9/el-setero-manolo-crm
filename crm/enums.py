"""Allowed values for the enumerated fields.

Member names are in English (code); the stored values stay in Spanish, as defined
in the data model spreadsheet.
"""

from enum import StrEnum


class Role(StrEnum):
    """Role a company plays for the business."""

    CUSTOMER = "Cliente"
    SUPPLIER = "Proveedor"


class CompanyType(StrEnum):
    """Kind of business a company is."""

    RESTAURANT = "restaurante"
    GREENGROCER = "frutería"
    SHOP = "tienda"
    SUPERMARKET = "supermercado"
    DISTRIBUTOR = "distribuidor"
    CATERING = "catering"
    CANTEEN = "comedor"


class CustomerStatus(StrEnum):
    """Commercial status of a company as a customer."""

    CONTACTED = "Contactado"
    NOT_INTERESTED = "Nada interesado"
    SLIGHTLY_INTERESTED = "Poco interesado"
    INTERESTED = "Interesado"
    VERY_INTERESTED = "Muy interesado"
    CUSTOMER = "Cliente"
    LOST = "Perdido"


class SupplierStatus(StrEnum):
    """Status of a company as a supplier."""

    CONTACTED = "Contactado"
    ACTIVE = "Activo"
    INACTIVE = "Inactivo"


class InteractionType(StrEnum):
    """Kind of interaction with a company."""

    CALL = "Llamada"
    MEETING = "Reunión en persona"
    WHATSAPP = "WhatsApp"
    EMAIL = "Correo"
    OTHER = "Otro"


class Direction(StrEnum):
    """Who started the interaction."""

    INBOUND = "Entrante"
    OUTBOUND = "Saliente"


class InteractionSource(StrEnum):
    """Channel through which the interaction entered the system."""

    WHATSAPP = "whatsapp"
    EMAIL = "correo"
    CALL = "llamada"
    VOICE_NOTE = "nota_de_voz"
    MANUAL = "manual"


class ProcessingStatus(StrEnum):
    """Processing state of an interaction; a pending one wakes the agent."""

    PENDING = "pendiente"
    PROCESSING = "procesando"
    PROCESSED = "procesada"
    ERROR = "error"


class ProductFormat(StrEnum):
    """Presentation format of a product."""

    FRESH = "Fresco"
    FROZEN = "Congelado"
    DEHYDRATED = "Deshidratado"


class OrderStatus(StrEnum):
    """Lifecycle state of an order."""

    NEW = "Nuevo"
    NEGOTIATING_PRICE = "Acordando precio"
    AWAITING_CONFIRMATION = "Esperando confirmación"
    CONFIRMED = "Confirmado"
    DELIVERED = "Entregado"
    CANCELLED = "Cancelado"


class InvoiceStatus(StrEnum):
    """Stored invoice states. 'Paid' and 'overdue' are derived (see view invoice_balance)."""

    DRAFT = "borrador"
    ISSUED = "emitida"
    VOIDED = "anulada"


class InvoiceType(StrEnum):
    """Series an invoice belongs to (only VDA can be issued for now, see [invoicing] enabled_types)."""

    VDA = "VDA"
    AGRARIAN = "Agrario"
    COMPANY = "Empresa"


class EmailStatus(StrEnum):
    """Whether the invoice PDF has been emailed."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class PaymentMethod(StrEnum):
    """How a payment was made."""

    TRANSFER = "transferencia"
    CASH = "efectivo"
    CARD = "tarjeta"
    BIZUM = "bizum"
    OTHER = "otro"


class AllocationStatus(StrEnum):
    """State of a lot allocation to an order line."""

    RESERVED = "reservada"
    CONSUMED = "consumida"
    RELEASED = "liberada"


class AdjustmentReason(StrEnum):
    """Why stock was removed from a lot."""

    SHRINKAGE = "merma"
    EXPIRED = "caducado"
    SAMPLE = "muestra"
    GIFT = "regalo"
    INVENTORY_ERROR = "error de inventario"
    OTHER = "otro"


class AgentStatus(StrEnum):
    """Outcome of an agent execution."""

    SUCCESS = "correcta"
    ERROR = "error"
    NEEDS_REVIEW = "requiere_revisión"


class AlertType(StrEnum):
    """Kind of alert raised by an agent."""

    INSUFFICIENT_STOCK = "stock_insuficiente"
    EXPIRING_LOT = "lote_por_caducar"
    LOW_STOCK = "stock_bajo"
    NOTE_NEEDS_REVIEW = "nota_en_revision"
    MISSING_DELIVERY_DATE = "pedido_sin_fecha_entrega"
    NOTE_PROCESSED = "nota_procesada"
    INCOMPLETE_ORDER = "pedido_incompleto"


class AlertSeverity(StrEnum):
    """How urgent an alert is."""

    INFO = "info"
    WARNING = "aviso"
    CRITICAL = "critico"


class OrderDraftStatus(StrEnum):
    """State of an order the agent could not complete by itself."""

    PENDING = "pendiente"
    COMPLETED = "completada"
    DISCARDED = "descartada"
