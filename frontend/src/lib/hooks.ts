import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, apiBlob, qs } from './api'
import type {
  Company, CompanyDetail, Contact, CustomerStatus, Dashboard, Interaction, Invoice,
  InvoiceConfig, InvoicePayload, InvoiceTotals, Page, PreviewLinePayload, Product,
} from './types'

export function useDashboard() {
  return useQuery({ queryKey: ['dashboard'], queryFn: () => api<Dashboard>('/dashboard') })
}

export interface CompanyFilters {
  search?: string; role?: string; type?: string; customer_status?: string; city?: string
  page?: number; page_size?: number
}

export function useCompanies(filters: CompanyFilters) {
  return useQuery({
    queryKey: ['companies', filters],
    queryFn: () => api<Page<Company>>(`/companies${qs({ ...filters })}`),
    placeholderData: keepPreviousData,
  })
}

/** Every customer of the pipeline (one big page, grouped by status on the screen). */
export function usePipelineCompanies() {
  return useQuery({
    queryKey: ['companies', 'pipeline'],
    queryFn: () => api<Page<Company>>(`/companies${qs({ role: 'Cliente', page_size: 100 })}`),
  })
}

export function useCompany(id: string | undefined) {
  return useQuery({
    queryKey: ['company', id],
    queryFn: () => api<CompanyDetail>(`/companies/${id}`),
    enabled: !!id,
  })
}

export function useContacts(params: { company_id?: string; search?: string; page?: number }) {
  return useQuery({
    queryKey: ['contacts', params],
    queryFn: () => api<Page<Contact>>(`/contacts${qs({ ...params, page_size: 100 })}`),
    placeholderData: keepPreviousData,
  })
}

export interface InteractionFilters {
  company_id?: string; contact_id?: string; type?: string; processing_status?: string
  unassigned?: boolean; search?: string; page?: number
}

export function useInteractions(filters: InteractionFilters) {
  return useQuery({
    queryKey: ['interactions', filters],
    queryFn: () => api<Page<Interaction>>(`/interactions${qs({ ...filters })}`),
    placeholderData: keepPreviousData,
  })
}

/** Small helper: a mutation that refreshes every cached listing afterwards. */
export function useApiMutation<TVars, TResult>(fn: (vars: TVars) => Promise<TResult>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries(),
  })
}

/** Products; the invoice form only offers the active ones. */
export function useProducts(options: { activeOnly?: boolean; search?: string } = {}) {
  const { activeOnly = true, search } = options
  return useQuery({
    queryKey: ['products', activeOnly, search ?? ''],
    queryFn: () => api<Product[]>(`/products${qs({ search, active_only: activeOnly ? undefined : 'false' })}`),
    placeholderData: keepPreviousData,
  })
}

export const saveProduct = (id: string | undefined, data: Partial<Product>) =>
  id
    ? api<Product>(`/products/${id}`, { method: 'PATCH', json: data })
    : api<Product>('/products', { method: 'POST', json: data })

export function useInvoiceConfig() {
  return useQuery({ queryKey: ['invoice-config'], queryFn: () => api<InvoiceConfig>('/invoices/config') })
}

/** A value that follows `value` after it stays unchanged for `delay` ms (to avoid a request per keystroke). */
export function useDebounced<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return debounced
}

/** Amounts computed by the server for some lines (the same calculation that is saved). */
export function useInvoiceTotals(lines: PreviewLinePayload[]) {
  const debounced = useDebounced(lines)
  return useQuery({
    queryKey: ['invoice-totals', debounced],
    queryFn: () => previewInvoice(debounced),
    enabled: debounced.length > 0,
    placeholderData: keepPreviousData,
  })
}

export interface InvoiceFilters { search?: string; email_status?: string; page?: number }

export function useInvoices(filters: InvoiceFilters) {
  return useQuery({
    queryKey: ['invoices', filters],
    queryFn: () => api<Page<Invoice>>(`/invoices${qs({ ...filters })}`),
    placeholderData: keepPreviousData,
  })
}

export const previewInvoice = (lines: PreviewLinePayload[]) =>
  api<InvoiceTotals>('/invoices/preview', { method: 'POST', json: { lines } })

export const createInvoice = (data: InvoicePayload) =>
  api<Invoice>('/invoices', { method: 'POST', json: data })

export const resendInvoice = (id: string) => api<Invoice>(`/invoices/${id}/send`, { method: 'POST' })

/** Download the PDF of an invoice (the API needs the token, so a plain link would not work). */
export async function downloadInvoicePdf(invoice: Invoice) {
  const blob = await apiBlob(`/invoices/${invoice.id}/pdf`)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${invoice.invoice_number ?? 'factura'}.pdf`
  link.click()
  URL.revokeObjectURL(url)
}

/** City, province and country found in an address (all null when it cannot be resolved). */
export const parseAddress = (q: string) =>
  api<{ city: string | null; region: string | null; country: string | null }>(`/geocoding/address?q=${encodeURIComponent(q)}`)

export const saveCompany = (id: string | undefined, data: Partial<Company>) =>
  id
    ? api<CompanyDetail>(`/companies/${id}`, { method: 'PATCH', json: data })
    : api<CompanyDetail>('/companies', { method: 'POST', json: data })

export const saveContact = (id: string | undefined, data: Partial<Contact>) =>
  id
    ? api<Contact>(`/contacts/${id}`, { method: 'PATCH', json: data })
    : api<Contact>('/contacts', { method: 'POST', json: data })

export const deleteContact = (id: string) => api<void>(`/contacts/${id}`, { method: 'DELETE' })

export const saveInteraction = (id: string | undefined, data: Record<string, unknown>) =>
  id
    ? api<Interaction>(`/interactions/${id}`, { method: 'PATCH', json: data })
    : api<Interaction>('/interactions', { method: 'POST', json: data })

export const moveCompany = (id: string, customer_status: CustomerStatus | null) =>
  api<Company>(`/companies/${id}/customer-status`, { method: 'PUT', json: { customer_status } })
