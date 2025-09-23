import React, { useState } from 'react'
import { echo, enhance } from '../api'

export default function SupportWorkflow(): JSX.Element {
  const [text, setText] = useState('Hello from React!')
  const [instructions, setInstructions] = useState(
    'Explain the likely cause of this issue and provide clear resolution steps using any knowledge base context provided.'
  )
  const [loading, setLoading] = useState(false)
  const [enhancing, setEnhancing] = useState(false)
  const [response, setResponse] = useState('')
  const [enhancedText, setEnhancedText] = useState('')
  const [error, setError] = useState('')

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

  const resolve = async () => {
    setEnhancing(true)
    setError('')
    try {
      const data = await enhance({ text, instructions })
      setEnhancedText(data.enhanced)
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Resolution failed')
    } finally {
      setEnhancing(false)
    }
  }

  return (
    <section>
      <p>Submit an error message or log snippet and generate a resolution using the knowledge base.</p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{ flex: 1, padding: '8px 12px' }}
          placeholder="Describe the issue or paste an error message"
        />
        <button onClick={send} disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </button>
        <button onClick={resolve} disabled={enhancing || !text.trim()}>
          {enhancing ? 'Resolving…' : 'Resolve using knowledge base'}
        </button>
      </div>
      <label style={{ display: 'block', marginBottom: 8 }}>
        Resolution guidance (optional):
        <input
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          style={{ width: '100%', marginTop: 4, padding: '6px 10px' }}
        />
      </label>
      {response && <pre style={{ background: '#f5f5f5', padding: 12, marginTop: 12 }}>{response}</pre>}
      {enhancedText && (
        <div style={{ marginTop: 16 }}>
          <h2 style={{ marginBottom: 6 }}>Proposed Resolution</h2>
          <pre style={{ background: '#eef5ff', padding: 12, whiteSpace: 'pre-wrap' }}>{enhancedText}</pre>
        </div>
      )}
      {error && <div style={{ color: 'red', marginTop: 12 }}>Error: {error}</div>}
      <hr style={{ margin: '2rem 0' }} />
      <p>
        Health check endpoint: <code>/healthz</code>
        <br />
        API endpoint: <code>/api/echo</code>
      </p>
    </section>
  )
}
