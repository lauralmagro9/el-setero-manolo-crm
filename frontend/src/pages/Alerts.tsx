import AlertList from '@/components/AlertList'
import { PageHeader } from '@/components/ui'

/** The alerts raised by the agents. */
export default function AlertsPage() {
  return (
    <>
      <PageHeader title="Alertas" />
      <AlertList />
    </>
  )
}
