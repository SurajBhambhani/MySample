import React, { useEffect, useState } from 'react'
import { ragGetStores, ragImport, ragSearch, ragUpload, RagSearchMatch } from '../api'

export default function KnowledgeBaseSection(): JSX.Element {
  const [ragUrls, setRagUrls] = useState('')
  const [ragStore, setRagStore] = useState('')
  const [ragSourcePrefix, setRagSourcePrefix] = useState('')
  const [ragFiles, setRagFiles] = useState<FileList | null>(null)
  const [ragStatus, setRagStatus] = useState('')
  const [ragStores, setRagStores] = useState<string[]>([])
  const [ragImporting, setRagImporting] = useState(false)
  const [ragSearching, setRagSearching] = useState(false)
  const [ragQuery, setRagQuery] = useState('')
  const [ragResults, setRagResults] = useState<RagSearchMatch[]>([])
  const [ragStoreFilter, setRagStoreFilter] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const loadStores = async () => {
      try {
        const stores = await ragGetStores()
        setRagStores(stores)
      } catch (err) {
        console.warn('Failed to fetch RAG stores', err)
      }
    }
    loadStores()
  }, [])

  const handleImportUrls = async () => {
    const urls = ragUrls
      .split(/\s|,|;|\n/)
      .map((value) => value.trim())
      .filter(Boolean)
    if (urls.length === 0) {
      setRagStatus('Add at least one URL to import.')
      return
    }
    setRagImporting(true)
    setRagStatus('')
    setError('')
    try {
      const res = await ragImport({
        urls,
        store: ragStore || undefined,
        source_prefix: ragSourcePrefix || undefined,
      })
      setRagStatus(`Imported ${res.items.length} item(s) into RAG.`)
      const stores = await ragGetStores()
      setRagStores(stores)
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'RAG import failed')
    } finally {
      setRagImporting(false)
    }
  }

  const handleUploadFiles = async () => {
    if (!ragFiles || ragFiles.length === 0) {
      setRagStatus('Select at least one file to upload.')
      return
    }
    setRagImporting(true)
    setRagStatus('')
    setError('')
    try {
      const files = Array.from(ragFiles)
      const res = await ragUpload(files, {
        store: ragStore || undefined,
        sourcePrefix: ragSourcePrefix || undefined,
      })
      setRagStatus(`Uploaded ${res.items.length} file(s) into RAG.`)
      const stores = await ragGetStores()
      setRagStores(stores)
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'RAG upload failed')
    } finally {
      setRagImporting(false)
    }
  }

  const handleRagSearch = async () => {
    if (!ragQuery.trim()) {
      setRagStatus('Enter a query to search the knowledge base.')
      return
    }
    setRagSearching(true)
    setRagStatus('')
    setError('')
    try {
      const res = await ragSearch(ragQuery, {
        store: ragStoreFilter || undefined,
        limit: 5,
      })
      setRagResults(res.results)
      setRagStatus(`Found ${res.results.length} match(es).`)
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'RAG search failed')
    } finally {
      setRagSearching(false)
    }
  }

  return (
    <section>
      <h2>Knowledge Base (RAG)</h2>
      <p style={{ marginBottom: 12 }}>
        Provide URLs, upload supporting files, or search the knowledge base. Resolutions will cite any matches found in the
        RAG data.
      </p>
      <div style={{ display: 'grid', gap: 12 }}>
        <label style={{ display: 'block' }}>
          URLs (comma, newline, or space separated):
          <textarea
            value={ragUrls}
            onChange={(e) => setRagUrls(e.target.value)}
            rows={3}
            style={{ width: '100%', marginTop: 4, padding: 8 }}
            placeholder="https://example.com/doc.pdf"
          />
        </label>
        <label style={{ display: 'block' }}>
          Store name (optional):
          <input
            value={ragStore}
            onChange={(e) => setRagStore(e.target.value)}
            placeholder="sqlite:rag_store.db"
            style={{ width: '100%', marginTop: 4, padding: 8 }}
          />
        </label>
        <label style={{ display: 'block' }}>
          Source prefix (optional):
          <input
            value={ragSourcePrefix}
            onChange={(e) => setRagSourcePrefix(e.target.value)}
            placeholder="Manual source name"
            style={{ width: '100%', marginTop: 4, padding: 8 }}
          />
        </label>
        <button onClick={handleImportUrls} disabled={ragImporting} style={{ alignSelf: 'flex-start' }}>
          {ragImporting ? 'Importing...' : 'Import URLs'}
        </button>
        <label style={{ display: 'block' }}>
          Upload files:
          <input type="file" multiple onChange={(event) => setRagFiles(event.target.files)} style={{ marginTop: 4 }} />
        </label>
        <button onClick={handleUploadFiles} disabled={ragImporting} style={{ alignSelf: 'flex-start' }}>
          {ragImporting ? 'Uploading...' : 'Upload files to RAG'}
        </button>
      </div>
      <div style={{ marginTop: 24 }}>
        <h3>Search Knowledge Base</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <input value={ragQuery} onChange={(e) => setRagQuery(e.target.value)} placeholder="Search query" style={{ padding: 8 }} />
          <input
            value={ragStoreFilter}
            onChange={(e) => setRagStoreFilter(e.target.value)}
            placeholder="Store filter (comma separated)"
            style={{ padding: 8 }}
          />
          <button onClick={handleRagSearch} disabled={ragSearching} style={{ alignSelf: 'flex-start' }}>
            {ragSearching ? 'Searching...' : 'Search RAG'}
          </button>
        </div>
        {ragStatus && <div style={{ marginTop: 12 }}>{ragStatus}</div>}
        {error && <div style={{ color: 'red', marginTop: 12 }}>{error}</div>}
        {ragStores.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <strong>Available stores:</strong> {ragStores.join(', ')}
          </div>
        )}
        {ragResults.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h4>Matches</h4>
            <ol style={{ paddingLeft: 20 }}>
              {ragResults.map((match) => (
                <li key={match.id} style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 600 }}>
                    {match.source || match.id} ({match.store || 'default'}) — score {match.score.toFixed(3)}
                  </div>
                  <div style={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap', background: '#f9f9f9', padding: 8 }}>
                    {match.snippet}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </section>
  )
}
