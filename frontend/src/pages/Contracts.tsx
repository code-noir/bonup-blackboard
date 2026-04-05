import { useState } from 'react'

const STATUS_STYLES: Record<string, { background: string; color: string }> = {
  ACTIVE:    { background: '#0F1F3D', color: '#FFFFFF' },
  PENDING:   { background: '#F59E0B', color: '#1F2937' },
  OVERDUE:   { background: '#EF4444', color: '#FFFFFF' },
  COMPLETED: { background: '#9CA3AF', color: '#FFFFFF' },
}

const CONTRACTS = [
  { name: 'Meridian Labs — Q2 Services',    party: 'Meridian Labs',   status: 'ACTIVE',    nextDue: '2026-05-01' },
  { name: 'Vanta Digital Retainer',          party: 'Vanta Digital',   status: 'PENDING',   nextDue: '2026-04-18' },
  { name: 'Orin Staffing Agreement',         party: 'Orin Staffing',   status: 'OVERDUE',   nextDue: '2026-04-03' },
  { name: 'Clearpath Inc — Delivery SLA',   party: 'Clearpath Inc',   status: 'COMPLETED', nextDue: '—'          },
  { name: 'Fenix Creative Studio Contract', party: 'Fenix Creative',  status: 'ACTIVE',    nextDue: '2026-07-01' },
]

const CARD: React.CSSProperties = {
  background: '#fff',
  borderRadius: 11,
  border: '1px solid rgba(0,0,0,0.05)',
}

const TH: React.CSSProperties = {
  fontSize: 11,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: '#9CA3AF',
  fontWeight: 500,
  padding: '0 12px 12px 0',
  textAlign: 'left',
  whiteSpace: 'nowrap',
}

const TD: React.CSSProperties = {
  fontSize: 13,
  color: '#374151',
  padding: '13px 12px 13px 0',
}

export default function Contracts() {
  const [hoveredRow, setHoveredRow] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState(0)
  const [isHovered, setIsHovered] = useState(false)
  const [selectedVideo, setSelectedVideo] = useState(0)
  const [isExpanded, setIsExpanded] = useState(false)
  const [message, setMessage] = useState('')
  const [chat, setChat] = useState([
    {
      role: 'ai',
      text: 'Hi! I can help you understand contracts, obligations, and how to get started. What would you like to know?',
    },
  ])

  function sendMessage() {
    const trimmed = message.trim()
    if (!trimmed) return
    setChat((prev) => [...prev, { role: 'user', text: trimmed }])
    setMessage('')
    // Placeholder AI response
    setTimeout(() => {
      setChat((prev) => [
        ...prev,
        { role: 'ai', text: 'This AI assistant is coming soon. Stay tuned!' },
      ])
    }, 600)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') sendMessage()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── SECTION 1: HOVER TAB SYSTEM ── */}
      <div
        style={{ position: 'relative' }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Create a Contract button — absolute top right */}
        <div style={{ position: 'absolute', top: 9, right: 22, zIndex: 1 }}>
          <button
            style={{
              background: '#000000',
              color: '#fff',
              fontSize: 13,
              fontWeight: 500,
              height: 34,
              padding: '0 18px',
              borderRadius: 8,
              border: 'none',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Create a Contract
          </button>
        </div>

        {/* Tab row */}
        <div
          style={{
            background: '#fff',
            borderRadius: isHovered ? '11px 11px 0 0' : 11,
            border: '1px solid rgba(0,0,0,0.05)',
            borderBottom: isHovered ? '1px solid #E5E7EB' : '1px solid rgba(0,0,0,0.05)',
            padding: '0 22px',
            display: 'flex',
            gap: 0,
          }}
        >
          {['My Contracts', 'Pending Review', 'Active Obligations', 'Negotiations', 'Expiring Soon', 'Archived'].map((tab, i) => (
            <div
              key={i}
              onMouseEnter={() => setActiveTab(i)}
              style={{
                padding: '18px 24px',
                fontSize: 15,
                fontWeight: 600,
                color: activeTab === i ? '#0F1F3D' : '#9CA3AF',
                borderBottom: activeTab === i ? '2px solid #F5A623' : '2px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.2s',
                marginBottom: -1,
                userSelect: 'none' as const,
              }}
            >
              {tab}
            </div>
          ))}
        </div>

        {/* Content area — visible only while hovering the wrapper */}
        {isHovered && (
          <div
            style={{
              background: '#fff',
              borderRadius: '0 0 11px 11px',
              border: '1px solid rgba(0,0,0,0.05)',
              borderTop: 'none',
              padding: '0 22px 20px',
              minHeight: 200,
            }}
          >

            {/* Helper: contract-style table */}
            {[0, 1, 4, 5].includes(activeTab) && (() => {
              const rows =
                activeTab === 0 ? CONTRACTS :
                activeTab === 1 ? [
                  { name: 'Vanta Digital Retainer',    party: 'Vanta Digital',  status: 'PENDING', nextDue: '2026-04-18' },
                  { name: 'Nexus SaaS Agreement',      party: 'Nexus SaaS',     status: 'PENDING', nextDue: '2026-04-25' },
                ] :
                activeTab === 4 ? [
                  { name: 'Vanta Digital Retainer',    party: 'Vanta Digital',  status: 'ACTIVE',  nextDue: '2026-04-18' },
                  { name: 'Orin Staffing Agreement',   party: 'Orin Staffing',  status: 'OVERDUE', nextDue: '2026-04-03' },
                ] : [
                  { name: 'Clearpath Inc — Delivery SLA',  party: 'Clearpath Inc',  status: 'COMPLETED', nextDue: '—' },
                  { name: 'Atlas Corp Q1 Contract',         party: 'Atlas Corp',     status: 'COMPLETED', nextDue: '—' },
                ]
              return (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 16 }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #F3F4F6' }}>
                        <th style={TH}>Contract Name</th>
                        <th style={TH}>Party</th>
                        <th style={TH}>Status</th>
                        <th style={TH}>Next Due Date</th>
                        <th style={{ ...TH, paddingRight: 0 }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, i) => (
                        <tr
                          key={i}
                          style={{
                            borderBottom: i < rows.length - 1 ? '1px solid #F3F4F6' : 'none',
                            background: hoveredRow === i ? '#F9FAFB' : 'transparent',
                            transition: 'background 0.1s',
                          }}
                          onMouseEnter={() => setHoveredRow(i)}
                          onMouseLeave={() => setHoveredRow(null)}
                        >
                          <td style={{ ...TD, fontWeight: 500 }}>{row.name}</td>
                          <td style={TD}>{row.party}</td>
                          <td style={TD}>
                            <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', ...STATUS_STYLES[row.status] }}>
                              {row.status}
                            </span>
                          </td>
                          <td style={{ ...TD, color: '#6B7280' }}>{row.nextDue}</td>
                          <td style={{ ...TD, paddingRight: 0 }}>
                            <button style={{ fontSize: 12, fontWeight: 500, color: '#0F1F3D', background: 'transparent', border: '1px solid #000', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', whiteSpace: 'nowrap' }}>
                              View →
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            })()}

            {/* Tab 2: Active Obligations */}
            {activeTab === 2 && (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 16 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #F3F4F6' }}>
                      <th style={TH}>Obligation</th>
                      <th style={TH}>Contract</th>
                      <th style={TH}>Status</th>
                      <th style={{ ...TH, paddingRight: 0 }}>Due Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { obligation: 'Monthly Payment — Apr', contract: 'Meridian Labs Q2',       status: 'ACTIVE', dueDate: '2026-04-10' },
                      { obligation: 'Delivery Milestone 2',  contract: 'Orin Staffing Agreement', status: 'ACTIVE', dueDate: '2026-04-14' },
                      { obligation: 'Quarterly Review',      contract: 'Fenix Creative Studio',   status: 'ACTIVE', dueDate: '2026-04-20' },
                    ].map((row, i, arr) => (
                      <tr
                        key={i}
                        style={{
                          borderBottom: i < arr.length - 1 ? '1px solid #F3F4F6' : 'none',
                          background: hoveredRow === i ? '#F9FAFB' : 'transparent',
                          transition: 'background 0.1s',
                        }}
                        onMouseEnter={() => setHoveredRow(i)}
                        onMouseLeave={() => setHoveredRow(null)}
                      >
                        <td style={{ ...TD, fontWeight: 500 }}>{row.obligation}</td>
                        <td style={TD}>{row.contract}</td>
                        <td style={TD}>
                          <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', ...STATUS_STYLES[row.status] }}>
                            {row.status}
                          </span>
                        </td>
                        <td style={{ ...TD, paddingRight: 0, color: '#6B7280' }}>{row.dueDate}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Tab 3: Negotiations */}
            {activeTab === 3 && (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 16 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #F3F4F6' }}>
                      <th style={TH}>Contract</th>
                      <th style={TH}>Version</th>
                      <th style={TH}>Parties</th>
                      <th style={{ ...TH, paddingRight: 0 }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { contract: 'Clearpath Partnership',   version: 'v0.3', parties: 'bonUP, Clearpath Inc',   status: 'PENDING' },
                      { contract: 'Vantage Consulting MSA',  version: 'v0.1', parties: 'bonUP, Vantage Group',   status: 'PENDING' },
                    ].map((row, i, arr) => (
                      <tr
                        key={i}
                        style={{
                          borderBottom: i < arr.length - 1 ? '1px solid #F3F4F6' : 'none',
                          background: hoveredRow === i ? '#F9FAFB' : 'transparent',
                          transition: 'background 0.1s',
                        }}
                        onMouseEnter={() => setHoveredRow(i)}
                        onMouseLeave={() => setHoveredRow(null)}
                      >
                        <td style={{ ...TD, fontWeight: 500 }}>{row.contract}</td>
                        <td style={{ ...TD, color: '#6B7280', fontFamily: 'monospace' }}>{row.version}</td>
                        <td style={TD}>{row.parties}</td>
                        <td style={{ ...TD, paddingRight: 0 }}>
                          <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', ...STATUS_STYLES[row.status] }}>
                            {row.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

          </div>
        )}
      </div>

      {/* ── SECTIONS 2 & 3: bottom half grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

        {/* SECTION 2 — CONTRACT TUTORIALS */}
        {(() => {
          const videos = [
            'How to create a contract',
            'Understanding obligations',
            'How to negotiate a contract',
            'Signing and rejecting versions',
            'Using contract templates',
            'Managing payments in Blackboard',
            'How Live Sessions work',
            'What is a PBVD?',
            'Sol groups explained',
            'Role switching guide',
          ]
          return (
            <div style={{ ...CARD, padding: 20, display: 'flex', flexDirection: 'row', gap: 16 }}>

              {/* Playlist — hidden when expanded */}
              {!isExpanded && (
                <div style={{ width: 220, flexShrink: 0 }}>
                  <p style={{ fontSize: 16, fontWeight: 700, color: '#0F1F3D', margin: '0 0 16px 0' }}>
                    Contract Tutorials
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {videos.map((title, i) => (
                      <button
                        key={i}
                        onClick={() => setSelectedVideo(i)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 10,
                          padding: '10px 12px',
                          borderRadius: 8,
                          cursor: 'pointer',
                          border: 'none',
                          background: selectedVideo === i ? '#F3F0FF' : 'transparent',
                          textAlign: 'left',
                          width: '100%',
                          transition: 'background 0.1s',
                        }}
                        onMouseEnter={(e) => {
                          if (selectedVideo !== i)
                            (e.currentTarget as HTMLButtonElement).style.background = '#F9FAFB'
                        }}
                        onMouseLeave={(e) => {
                          if (selectedVideo !== i)
                            (e.currentTarget as HTMLButtonElement).style.background = 'transparent'
                        }}
                      >
                        <span
                          style={{
                            fontSize: 9,
                            color: selectedVideo === i ? '#8B5CF6' : '#9CA3AF',
                            lineHeight: 1,
                          }}
                        >
                          ▶
                        </span>
                        <span
                          style={{
                            fontSize: 12,
                            color: selectedVideo === i ? '#0F1F3D' : '#374151',
                            fontWeight: selectedVideo === i ? 500 : 400,
                            lineHeight: 1.4,
                          }}
                        >
                          {title}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Player */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: '#0F1F3D', margin: '0 0 10px 0' }}>
                  {videos[selectedVideo]}
                </p>

                {/* Player area */}
                <div
                  style={{
                    width: '100%',
                    aspectRatio: '16 / 9',
                    background: '#1C2B3A',
                    borderRadius: 8,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: '50%',
                      background: 'rgba(255,255,255,0.15)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <span style={{ color: '#fff', fontSize: 18, marginLeft: 3 }}>▶</span>
                  </div>
                  <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', margin: 0 }}>
                    Tutorial coming soon
                  </p>
                </div>

                {/* Expand / Collapse toggle */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
                  <button
                    onClick={() => setIsExpanded((v) => !v)}
                    style={{
                      fontSize: 11,
                      color: '#9CA3AF',
                      cursor: 'pointer',
                      border: 'none',
                      background: 'transparent',
                      padding: 0,
                    }}
                  >
                    {isExpanded ? '⤡ Collapse' : '⤢ Expand'}
                  </button>
                </div>

                {/* Create a Contract */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
                  <button
                    style={{
                      background: '#F5A623',
                      color: '#0F1F3D',
                      fontSize: 13,
                      fontWeight: 600,
                      height: 34,
                      padding: '0 18px',
                      borderRadius: 8,
                      border: 'none',
                      cursor: 'pointer',
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = '#D4900A' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = '#F5A623' }}
                  >
                    Create a Contract
                  </button>
                </div>
              </div>

            </div>
          )
        })()}

        {/* SECTION 3 — ASK AI */}
        <div
          style={{
            ...CARD,
            padding: 20,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <p style={{ fontSize: 16, fontWeight: 700, color: '#0F1F3D', margin: '0 0 16px 0' }}>
            Ask AI about contracts
          </p>

          {/* Chat area */}
          <div
            style={{
              flex: 1,
              minHeight: 180,
              background: '#F9FAFB',
              borderRadius: 8,
              padding: 12,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            {chat.map((msg, i) =>
              msg.role === 'ai' ? (
                <div key={i} style={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <span
                    style={{
                      background: '#E8F4FD',
                      color: '#0F1F3D',
                      borderRadius: 8,
                      padding: '10px 14px',
                      fontSize: 13,
                      maxWidth: '85%',
                      lineHeight: 1.5,
                    }}
                  >
                    {msg.text}
                  </span>
                </div>
              ) : (
                <div key={i} style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <span
                    style={{
                      background: '#0F1F3D',
                      color: '#fff',
                      borderRadius: 8,
                      padding: '10px 14px',
                      fontSize: 13,
                      maxWidth: '85%',
                      lineHeight: 1.5,
                    }}
                  >
                    {msg.text}
                  </span>
                </div>
              )
            )}
          </div>

          {/* Input bar */}
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question…"
              style={{
                flex: 1,
                background: '#fff',
                border: '1px solid #E5E7EB',
                borderRadius: 8,
                fontSize: 13,
                padding: '8px 12px',
                outline: 'none',
                color: '#374151',
              }}
            />
            <button
              onClick={sendMessage}
              style={{
                background: '#000',
                color: '#fff',
                border: 'none',
                borderRadius: 8,
                padding: '0 16px',
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              Send
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}
