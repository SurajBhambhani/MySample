import axios from 'axios'

// Prefer proxy (dev) or same-origin (prod). Allow override via VITE_API_BASE_URL.
const baseURL = import.meta.env.VITE_API_BASE_URL || ''

export const api = axios.create({ baseURL })

export type EchoResponse = { message: string; length: number }

export async function echo(message: string): Promise<EchoResponse> {
  const res = await api.post<EchoResponse>('/api/echo', { message })
  return res.data
}

