import React, { useState } from 'react'
import { echo } from './api'

export default function App() {
  const [text, setText] = useState('Hello from React!')
  const [response, setResponse] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')

  const send = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await echo(text)
      setResponse(`Echo: "${data.message}" (length=${data.length})`)
    } catch (e: any) {
      setError(e?.message || 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 640, margin: '3rem auto', fontFamily: 'Inter, system-ui, Arial' }}>
      <h1>Vite + React + FastAPI</h1>
      <p>Type a message and send it to the FastAPI backend:</p>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{ flex: 1, padding: '8px 12px' }}
          placeholder="Type here"
        />
        <button onClick={send} disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </button>
      </div>
      {response && (
        <pre style={{ background: '#f5f5f5', padding: 12, marginTop: 12 }}>{response}</pre>
      )}
      {error && (
        <div style={{ color: 'red', marginTop: 12 }}>Error: {error}</div>
      )}
      <hr style={{ margin: '2rem 0' }} />
      <p>
        Health check endpoint: <code>/healthz</code><br />
        API endpoint: <code>/api/echo</code>
      </p>
    </div>
  )
}

