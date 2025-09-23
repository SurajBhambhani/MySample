import React, { useState } from 'react'
import SupportWorkflow from './components/SupportWorkflow'
import KnowledgeBaseSection from './components/KnowledgeBaseSection'

export default function App(): JSX.Element {
  const [activeTab, setActiveTab] = useState<'support' | 'knowledge'>('support')

  return (
    <div style={{ maxWidth: 720, margin: '3rem auto', fontFamily: 'Inter, system-ui, Arial' }}>
      <h1>MCP Relay</h1>
      <nav style={{ display: 'flex', gap: 12, margin: '1.5rem 0' }}>
        <button
          onClick={() => setActiveTab('support')}
          style={{
            padding: '8px 16px',
            borderRadius: 8,
            border: '1px solid #ccc',
            background: activeTab === 'support' ? '#1f6feb' : '#f5f5f5',
            color: activeTab === 'support' ? '#fff' : '#333',
            cursor: 'pointer',
          }}
        >
          Support Workflow
        </button>
        <button
          onClick={() => setActiveTab('knowledge')}
          style={{
            padding: '8px 16px',
            borderRadius: 8,
            border: '1px solid #ccc',
            background: activeTab === 'knowledge' ? '#1f6feb' : '#f5f5f5',
            color: activeTab === 'knowledge' ? '#fff' : '#333',
            cursor: 'pointer',
          }}
        >
          Knowledge Base
        </button>
      </nav>

      {activeTab === 'support' ? <SupportWorkflow /> : <KnowledgeBaseSection />}
    </div>
  )
}
