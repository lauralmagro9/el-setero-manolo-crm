import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import { useAuth } from './lib/auth'
import CompanyDetailPage from './pages/CompanyDetail'
import CompaniesPage from './pages/Companies'
import ContactsPage from './pages/Contacts'
import DashboardPage from './pages/Dashboard'
import InteractionsPage from './pages/Interactions'
import InvoicesPage from './pages/Invoices'
import NewInvoicePage from './pages/NewInvoice'
import LoginPage from './pages/Login'
import PipelinePage from './pages/Pipeline'
import ProductsPage from './pages/Products'
import RecordPage from './pages/Record'

export default function App() {
  const { session, loading } = useAuth()
  if (loading) return <Spinner />
  if (!session) return <LoginPage />
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="empresas" element={<CompaniesPage />} />
        <Route path="empresas/:id" element={<CompanyDetailPage />} />
        <Route path="pipeline" element={<PipelinePage />} />
        <Route path="contactos" element={<ContactsPage />} />
        <Route path="interacciones" element={<InteractionsPage />} />
        <Route path="facturas" element={<InvoicesPage />} />
        <Route path="facturas/nueva" element={<NewInvoicePage />} />
        <Route path="productos" element={<ProductsPage />} />
        <Route path="grabar" element={<RecordPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
