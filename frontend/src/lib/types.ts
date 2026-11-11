/** Values accepted by the API (they mirror enums.py; the stored values are Spanish). */
export const ROLES = ['Cliente', 'Proveedor'] as const
export const COMPANY_TYPES = [
  'restaurante', 'frutería', 'tienda', 'supermercado', 'distribuidor', 'catering', 'comedor',
] as const
export const CUSTOMER_STATUSES = [
  'Contactado', 'Nada interesado', 'Poco interesado', 'Interesado', 'Muy interesado', 'Cliente', 'Perdido',
] as const
export const SUPPLIER_STATUSES = ['Contactado', 'Activo', 'Inactivo'] as const
export const INTERACTION_TYPES = ['Llamada', 'Reunión en persona', 'WhatsApp', 'Correo', 'Otro'] as const
export const DIRECTIONS = ['Entrante', 'Saliente'] as const
export const PROCESSING_STATUSES = ['pendiente', 'procesando', 'procesada', 'error'] as const

export type Role = (typeof ROLES)[number]
export type CompanyType = (typeof COMPANY_TYPES)[number]
export type CustomerStatus = (typeof CUSTOMER_STATUSES)[number]
export type SupplierStatus = (typeof SUPPLIER_STATUSES)[number]
export type InteractionType = (typeof INTERACTION_TYPES)[number]
export type Direction = (typeof DIRECTIONS)[number]
export type ProcessingStatus = (typeof PROCESSING_STATUSES)[number]

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface CompanyRef { id: string; name: string }
export interface ContactRef { id: string; first_name: string; last_name: string | null }

export interface Company {
  id: string
  name: string
  tax_id: string | null
  billing_name: string | null
  billing_address: string | null
  website: string | null
  phone: string | null
  email: string | null
  address: string | null
  city: string | null
  region: string | null
  country: string | null
  roles: Role[]
  type: CompanyType[]
  customer_status: CustomerStatus | null
  supplier_status: SupplierStatus | null
  description: string | null
}

export interface Contact {
  id: string
  company_id: string
  first_name: string
  last_name: string | null
  position: string | null
  phone: string | null
  email: string | null
  is_primary: boolean
  summary: string | null
  company: CompanyRef
}

export interface CompanyDetail extends Company { contacts: Contact[] }

export interface Interaction {
  id: string
  company_id: string | null
  contact_id: string | null
  occurred_at: string
  type: InteractionType
  direction: Direction | null
  summary: string | null
  notes: string | null
  source: string
  transcript: string | null
  processing_status: ProcessingStatus
  created_by: string | null
  company: CompanyRef | null
  contact: ContactRef | null
}

export interface LotAlert {
  lot_id: string
  product_name: string
  lot_code: string
  expiry_date: string | null
  available_quantity: string
  status: string
}

export const INVOICE_TYPES = ['VDA', 'Agrario', 'Empresa'] as const
export type InvoiceType = (typeof INVOICE_TYPES)[number]
export type EmailStatus = 'pending' | 'sent' | 'failed'

export const PRODUCT_FORMATS = ['Fresco', 'Congelado', 'Deshidratado'] as const
export type ProductFormat = (typeof PRODUCT_FORMATS)[number]

export interface Product {
  id: string
  name: string
  species: string | null
  format: ProductFormat
  description: string | null
  base_unit: string
  is_active: boolean
  tax_rate: string // fraction: 0.10 = 10 %
  target_net_margin: string // fraction
}

export interface InvoiceTotals {
  line_amounts: string[]
  taxable_base: string
  vat_rate: string
  vat_amount: string
  total: string
}

export interface InvoiceLine {
  id: string
  product_id: string | null
  product_name: string | null
  description: string
  unit: string
  quantity: string
  unit_price: string
  tax_rate: string
}

export interface Invoice {
  id: string
  invoice_number: string | null
  invoice_type: InvoiceType
  issue_date: string | null
  operation_date: string | null
  status: string
  company_id: string | null
  customer_name: string | null
  customer_tax_id: string | null
  customer_address: string | null
  notes: string | null
  email_status: EmailStatus
  email_recipient: string | null
  email_sent_at: string | null
  email_error: string | null
  created_by: string | null
  items: InvoiceLine[]
  totals: InvoiceTotals | null
}

export interface InvoiceConfig { enabled_types: InvoiceType[]; vat_rate: string }

export interface InvoiceLinePayload {
  product_id: string
  description: string
  unit: string
  quantity: string
  unit_price: string
}

export interface PreviewLinePayload { quantity: string; unit_price: string }

/** A company created together with the invoice; every billing field is mandatory. */
export interface NewCompanyPayload {
  name: string
  roles: Role[]
  type: CompanyType[]
  billing_name: string
  billing_address: string
  tax_id: string
  [field: string]: unknown
}

/** Either `company_id` (existing company) or `new_company` (created with the invoice). */
export interface InvoicePayload {
  invoice_type: InvoiceType
  issue_date?: string | null
  operation_date?: string | null
  company_id?: string | null
  new_company?: NewCompanyPayload | null
  notes?: string | null
  lines: InvoiceLinePayload[]
}

export interface Dashboard {
  customers_by_status: { customer_status: CustomerStatus; count: number }[]
  interactions_short_window: number
  interactions_long_window: number
  short_window_days: number
  long_window_days: number
  pending_interactions: number
  unassigned_voice_notes: number
  expiring_lots: LotAlert[]
  low_stock_lots: LotAlert[]
  recent_interactions: Interaction[]
}
