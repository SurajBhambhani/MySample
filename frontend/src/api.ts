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
