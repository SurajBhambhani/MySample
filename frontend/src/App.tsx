import React, { useState } from 'react'
import { echo, enhance } from './api'

export default function App() {
  const [text, setText] = useState('Hello from React!')
  const [response, setResponse] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')
  const [enhancing, setEnhancing] = useState(false)
  const [enhancedText, setEnhancedText] = useState<string>('')
  const [instructions, setInstructions] = useState<string>('Make it more descriptive.')

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

  const enrich = async () => {
    setEnhancing(true)
    setError('')
    try {
      const data = await enhance({ text, instructions })
      setEnhancedText(data.enhanced)
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Enhancement failed')
    } finally {
      setEnhancing(false)
    }
  }

  return (
    <div style={{ maxWidth: 640, margin: '3rem auto', fontFamily: 'Inter, system-ui, Arial' }}>
      <h1>Vite + React + FastAPI</h1>
      <p>Type a message and send it to the FastAPI backend:</p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{ flex: 1, padding: '8px 12px' }}
          placeholder="Type here"
        />
        <button onClick={send} disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </button>
        <button onClick={enrich} disabled={enhancing || !text.trim()}>
          {enhancing ? 'Enhancing...' : 'Make more descriptive'}
        </button>
      </div>
      <label style={{ display: 'block', marginBottom: 8 }}>
        Instructions:
        <input
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          style={{ width: '100%', marginTop: 4, padding: '6px 10px' }}
        />
      </label>
      {response && (
        <pre style={{ background: '#f5f5f5', padding: 12, marginTop: 12 }}>{response}</pre>
      )}
      {enhancedText && (
        <div style={{ marginTop: 16 }}>
          <h2 style={{ marginBottom: 6 }}>Enhanced Text</h2>
          <pre style={{ background: '#eef5ff', padding: 12, whiteSpace: 'pre-wrap' }}>{enhancedText}</pre>
        </div>
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
