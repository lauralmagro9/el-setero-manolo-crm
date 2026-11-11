import { get, set } from 'idb-keyval'

/** A recording that could not be uploaded yet; kept in the browser until the server confirms it. */
export interface PendingRecording {
  id: string
  blob: Blob
  mimeType: string
  createdAt: string
  fields: { company_id?: string; contact_id?: string; type: string; occurred_at: string }
  error?: string
}

const KEY = 'pending-recordings'

export async function listPending(): Promise<PendingRecording[]> {
  return (await get<PendingRecording[]>(KEY)) ?? []
}

export async function addPending(item: PendingRecording): Promise<void> {
  await set(KEY, [...(await listPending()).filter((p) => p.id !== item.id), item])
}

export async function removePending(id: string): Promise<void> {
  await set(KEY, (await listPending()).filter((p) => p.id !== id))
}
