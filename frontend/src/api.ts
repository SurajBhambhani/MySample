import axios from 'axios'

// Prefer proxy (dev) or same-origin (prod). Allow override via VITE_API_BASE_URL.
const baseURL = import.meta.env.VITE_API_BASE_URL || ''

export const api = axios.create({ baseURL })

export type EchoResponse = { message: string; length: number }
export type EnhanceRequest = { text: string; instructions?: string; model?: string }
export type EnhanceResponse = {
  message_id: number | null
  enhanced_id: number | null
  original: string
  enhanced: string
  processing: {
    instructions: string
    model: string | null
    provider: string
    persisted?: boolean
    storage_error?: string
    rag?: unknown
  }
}

export async function echo(message: string): Promise<EchoResponse> {
  const res = await api.post<EchoResponse>('/api/echo', { message })
  return res.data
}

export async function enhance(body: EnhanceRequest): Promise<EnhanceResponse> {
  const res = await api.post<EnhanceResponse>('/api/enhance', body)
  return res.data
}

export type RagImportRequest = {
  urls?: string[]
  texts?: string[]
  store?: string
  source_prefix?: string
}

export type RagImportItem = {
  id: string
  source?: string | null
  store?: string | null
}

export type RagImportResponse = {
  items: RagImportItem[]
}

export type RagSearchMatch = {
  id: string
  source?: string | null
  store?: string | null
  score: number
  snippet: string
}

export type RagSearchResponse = {
  results: RagSearchMatch[]
}

export async function ragGetStores(): Promise<string[]> {
  const res = await api.get<string[]>('/api/rag/stores')
  return res.data
}

export async function ragImport(payload: RagImportRequest): Promise<RagImportResponse> {
  const res = await api.post<RagImportResponse>('/api/rag/import', payload)
  return res.data
}

export async function ragUpload(files: File[], options: { store?: string; sourcePrefix?: string } = {}): Promise<RagImportResponse> {
  const form = new FormData()
  files.forEach((file) => form.append('files', file))
  if (options.store) form.append('store', options.store)
  if (options.sourcePrefix) form.append('source_prefix', options.sourcePrefix)
  const res = await api.post<RagImportResponse>('/api/rag/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function ragSearch(query: string, options: { limit?: number; store?: string } = {}): Promise<RagSearchResponse> {
  const params: Record<string, string | number> = { query }
  if (options.limit) params.limit = options.limit
  if (options.store) params.store = options.store
  const res = await api.get<RagSearchResponse>('/api/rag/search', { params })
  return res.data
}
