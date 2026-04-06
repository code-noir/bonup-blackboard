import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api/client'
import type { BusinessEntity } from '@/types/entities'
import { useAuth } from '@/context/AuthContext'

const STATUS_STYLES: Record<string, { background: string; color: string }> = {
  ACTIVE:    { background: '#0F1F3D', color: '#FFFFFF' },
  PENDING:   { background: '#F59E0B', color: '#1F2937' },
  OVERDUE:   { background: '#EF4444', color: '#FFFFFF' },
  COMPLETED: { background: '#9CA3AF', color: '#FFFFFF' },
}

const STATUS_DARK: Record<string, { background: string; color: string }> = {
  ACTIVE:    { background: 'rgba(255,255,255,0.15)', color: '#ffffff' },
  PENDING:   { background: '#F5A623',                color: '#0F1F3D' },
  OVERDUE:   { background: '#DC2626',                color: '#ffffff' },
  COMPLETED: { background: 'rgba(255,255,255,0.1)',  color: 'rgba(255,255,255,0.6)' },
}

const TH_DARK: React.CSSProperties = {
  fontSize: 11,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: '#9CA3AF',
  fontWeight: 500,
  padding: '0 12px 8px 0',
  textAlign: 'left',
  whiteSpace: 'nowrap',
}

const TD_DARK: React.CSSProperties = {
  fontSize: 13,
  color: '#374151',
  padding: '8px 12px 8px 0',
}

interface ContractRow { id: string; name: string; party: string; status: string; nextDue: string }

function stateToStatus(state: string): string {
  if (state === 'fulfilled') return 'COMPLETED'
  if (state === 'at_risk') return 'OVERDUE'
  return 'ACTIVE'
}

function structureLabel(type: string): string {
  const map: Record<string, string> = {
    ONE_TIME: 'One-Time',
    ONGOING: 'Ongoing',
    COLLABORATIVE: 'Collaborative',
    RESOLUTION: 'Resolution',
  }
  return map[type] ?? type
}

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
  const navigate = useNavigate()
  const { user } = useAuth()
  const [hoveredRow, setHoveredRow] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState(0)
  const [entityFilter, setEntityFilter] = useState('All')
  const [contracts, setContracts] = useState<ContractRow[]>([])
  const [entities, setEntities] = useState<BusinessEntity[]>([])
  const [showEntityModal, setShowEntityModal] = useState(false)
  const [bizDropdownOpen, setBizDropdownOpen] = useState(false)
  const bizDropdownRef = useRef<HTMLDivElement>(null)

  const tier = user?.subscription_tier ?? ''
  const isEnterprise = tier === 'blackboard_enterprise'
  const isBusiness = tier === 'blackboard_business'
  const isPro = tier === 'blackboard_pro'
  const bizDropdownTier = isEnterprise || isBusiness

  // Close biz dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (bizDropdownRef.current && !bizDropdownRef.current.contains(e.target as Node)) {
        setBizDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function openCreateModal() {
    setShowEntityModal(true)
  }

  function handleSelectPersonal() {
    setShowEntityModal(false)
    navigate('/contracts/create?entity=personal')
  }

  function handleSelectBusiness(name: string) {
    setShowEntityModal(false)
    navigate(`/contracts/create?entity=business&name=${encodeURIComponent(name)}`)
  }

  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'You'
  const initials = ([user?.first_name?.[0], user?.last_name?.[0]].filter(Boolean).join('') || user?.username?.[0] || '?').toUpperCase()

  useEffect(() => {
    api.get<{ id: string; counterparty_email: string; structure_type: string; state: string }[]>('/contracts/')
      .then(({ data }) => {
        setContracts(data.map((c) => ({
          id: c.id,
          name: `${structureLabel(c.structure_type)} #${c.id.slice(-6).toUpperCase()}`,
          party: c.counterparty_email,
          status: stateToStatus(c.state),
          nextDue: '—',
        })))
      })
      .catch(() => {})

    api.get<{ results: BusinessEntity[] }>('/entities/')
      .then(({ data }) => setEntities(data.results))
      .catch(() => {})
  }, [])

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

      {/* ── ENTITY FILTER TABS ── */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        {/* All */}
        {['All', 'Personal'].map((tab) => (
          <button
            key={tab}
            onClick={() => setEntityFilter(tab)}
            style={{
              height: 30, padding: '0 14px',
              background: entityFilter === tab ? '#0F1F3D' : 'white',
              color: entityFilter === tab ? 'white' : '#6B7280',
              border: `1px solid ${entityFilter === tab ? '#0F1F3D' : '#E5E7EB'}`,
              borderRadius: 6, fontSize: 12, fontWeight: 500,
              cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => {
              if (entityFilter !== tab) {
                e.currentTarget.style.borderColor = '#9CA3AF'
                e.currentTarget.style.color = '#374151'
              }
            }}
            onMouseLeave={(e) => {
              if (entityFilter !== tab) {
                e.currentTarget.style.borderColor = '#E5E7EB'
                e.currentTarget.style.color = '#6B7280'
              }
            }}
          >
            {tab}
          </button>
        ))}

        {/* Business tab — dropdown for Enterprise/Business, direct for Pro */}
        {(bizDropdownTier || isPro) && (
          <div ref={bizDropdownRef} style={{ position: 'relative' }}>
            <button
              onClick={() => {
                if (isPro && entities.length === 1) {
                  setEntityFilter(entities[0].name)
                } else {
                  setBizDropdownOpen((v) => !v)
                  setEntityFilter('Business')
                }
              }}
              style={{
                height: 30, padding: '0 12px',
                background: entityFilter === 'Business' || entities.some(e => e.name === entityFilter) ? '#0F1F3D' : 'white',
                color: entityFilter === 'Business' || entities.some(e => e.name === entityFilter) ? 'white' : '#6B7280',
                border: `1px solid ${entityFilter === 'Business' || entities.some(e => e.name === entityFilter) ? '#0F1F3D' : '#E5E7EB'}`,
                borderRadius: 6, fontSize: 12, fontWeight: 500,
                cursor: 'pointer', transition: 'all 0.15s',
                display: 'flex', alignItems: 'center', gap: 4,
              }}
            >
              Business
              {bizDropdownTier && <span style={{ fontSize: 10, opacity: 0.7 }}>▾</span>}
            </button>

            {bizDropdownOpen && bizDropdownTier && (
              <div style={{
                position: 'absolute', top: 34, left: 0,
                background: 'white', borderRadius: 8,
                border: '1px solid #E5E7EB',
                boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
                minWidth: 180, zIndex: 100, overflow: 'hidden',
              }}>
                {entities.length === 0 ? (
                  <div style={{ padding: '10px 14px' }}>
                    <p style={{ fontSize: 12, color: '#9CA3AF', margin: '0 0 8px' }}>No businesses yet</p>
                    <span
                      onClick={() => { setBizDropdownOpen(false); navigate('/entities') }}
                      style={{ fontSize: 12, color: '#0F1F3D', fontWeight: 500, cursor: 'pointer' }}
                    >
                      + Add a Business
                    </span>
                  </div>
                ) : (
                  <>
                    {entities.map((e) => (
                      <div
                        key={e.id}
                        onClick={() => { setEntityFilter(e.name); setBizDropdownOpen(false) }}
                        style={{ padding: '9px 14px', fontSize: 13, color: '#374151', cursor: 'pointer' }}
                        onMouseEnter={(ev) => (ev.currentTarget.style.background = '#F3F4F6')}
                        onMouseLeave={(ev) => (ev.currentTarget.style.background = 'transparent')}
                      >
                        {e.name}
                      </div>
                    ))}
                    <div style={{ borderTop: '1px solid #E5E7EB', padding: '9px 14px' }}>
                      <span
                        onClick={() => { setBizDropdownOpen(false); navigate('/entities') }}
                        style={{ fontSize: 12, color: '#6B7280', cursor: 'pointer' }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = '#0F1F3D')}
                        onMouseLeave={(e) => (e.currentTarget.style.color = '#6B7280')}
                      >
                        + Add a Business
                      </span>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── ENTITY SELECTION MODAL ── */}
      {showEntityModal && (
        <>
          <div
            onClick={() => setShowEntityModal(false)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', zIndex: 499 }}
          />
          <div style={{
            position: 'fixed', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'white', borderRadius: 12,
            padding: 24, width: 320,
            boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
            zIndex: 500,
          }}>
            {/* Close */}
            <button
              onClick={() => setShowEntityModal(false)}
              style={{
                position: 'absolute', top: 12, right: 14,
                background: 'transparent', border: 'none',
                fontSize: 18, color: '#9CA3AF', cursor: 'pointer', lineHeight: 1,
              }}
            >
              ×
            </button>

            <p style={{ fontSize: 16, fontWeight: 600, color: '#0F1F3D', margin: '0 0 6px' }}>
              Who are you contracting as?
            </p>
            <p style={{ fontSize: 13, color: '#6B7280', margin: '0 0 20px' }}>
              Choose the identity for this contract
            </p>

            {/* Personal card */}
            <div
              onClick={handleSelectPersonal}
              style={{
                background: 'white', borderRadius: 10,
                border: '1px solid #E5E7EB',
                padding: '14px 16px', marginBottom: 10,
                cursor: 'pointer', display: 'flex',
                alignItems: 'center', gap: 12,
                transition: 'all 0.15s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#0F1F3D'
                e.currentTarget.style.background = '#F8FAFC'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#E5E7EB'
                e.currentTarget.style.background = 'white'
              }}
            >
              <div style={{
                width: 36, height: 36, borderRadius: '50%',
                background: '#0F1F3D', color: 'white',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 13, fontWeight: 600, flexShrink: 0,
              }}>
                {initials}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                  <span style={{ fontSize: 14, fontWeight: 500, color: '#0F1F3D' }}>{displayName}</span>
                  <span style={{
                    background: '#E5E7EB', color: '#374151',
                    fontSize: 11, padding: '2px 8px', borderRadius: 4,
                  }}>Personal</span>
                </div>
                {user?.bon_id && (
                  <span style={{ fontSize: 11, color: '#8B5CF6', fontFamily: 'DM Mono, monospace' }}>
                    {user.bon_id}
                  </span>
                )}
              </div>
            </div>

            {/* Business section */}
            <div style={{
              background: 'white', borderRadius: 10,
              border: '1px solid #E5E7EB',
              overflow: 'hidden',
            }}>
              {entities.length === 0 ? (
                <div style={{ padding: '14px 16px' }}>
                  <p style={{ fontSize: 13, color: '#9CA3AF', margin: '0 0 10px' }}>
                    No businesses added yet
                  </p>
                  <span
                    onClick={() => { setShowEntityModal(false); navigate('/entities') }}
                    style={{ fontSize: 13, color: '#0F1F3D', fontWeight: 500, cursor: 'pointer' }}
                  >
                    + Add a Business
                  </span>
                </div>
              ) : (
                <>
                  {entities.map((e) => (
                    <div
                      key={e.id}
                      onClick={() => handleSelectBusiness(e.name)}
                      style={{
                        padding: '14px 16px', display: 'flex',
                        alignItems: 'center', gap: 12,
                        cursor: 'pointer', borderBottom: '1px solid #F3F4F6',
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={(ev) => (ev.currentTarget.style.background = '#F8FAFC')}
                      onMouseLeave={(ev) => (ev.currentTarget.style.background = 'transparent')}
                    >
                      <div style={{
                        width: 36, height: 36, borderRadius: '50%',
                        background: '#F3F4F6', color: '#374151',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 13, fontWeight: 600, flexShrink: 0,
                      }}>
                        {e.name.substring(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 500, color: '#0F1F3D' }}>{e.name}</div>
                        <div style={{ fontSize: 11, color: '#9CA3AF' }}>{e.business_type}</div>
                      </div>
                    </div>
                  ))}
                  <div style={{ padding: '10px 16px' }}>
                    <span
                      onClick={() => { setShowEntityModal(false); navigate('/entities') }}
                      style={{ fontSize: 12, color: '#6B7280', cursor: 'pointer' }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#0F1F3D')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = '#6B7280')}
                    >
                      + Add a Business
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {/* ── SECTION 1: HOVER TAB SYSTEM ── */}
      <div
        style={{ position: 'relative' }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Create a Contract button — absolute top right */}
        <div style={{ position: 'absolute', top: 9, right: 22, zIndex: 1 }}>
          <button
            onClick={openCreateModal}
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
            borderRadius: 11,
            border: '1px solid rgba(0,0,0,0.05)',
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

        {/* Content area — max-height transition, normal document flow */}
        <div
          style={{
            maxHeight: isHovered ? '320px' : '0',
            overflow: 'hidden',
            opacity: isHovered ? 1 : 0,
            transition: 'max-height 0.5s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.4s ease',
            transitionDelay: isHovered ? '0s' : '0.1s',
          }}
        >
          <div
            style={{
              background: '#F0F4F8',
              borderRadius: '0 0 11px 11px',
              height: 320,
              overflowY: 'auto',
              padding: '0 22px 20px',
            }}
          >

            {/* Tabs 0, 1, 4, 5 — contract-style table */}
            {activeTab === 0 && contracts.length === 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 220, gap: 12 }}>
                <p style={{ fontSize: 14, color: '#9CA3AF', margin: 0 }}>
                  No contracts yet. Create your first contract.
                </p>
                <button
                  onClick={openCreateModal}
                  style={{ background: '#000000', color: '#fff', fontSize: 13, fontWeight: 500, height: 34, padding: '0 18px', borderRadius: 8, border: 'none', cursor: 'pointer' }}
                >
                  Create a Contract
                </button>
              </div>
            )}
            {[0, 1, 4, 5].includes(activeTab) && (activeTab !== 0 || contracts.length > 0) && (() => {
              const rows =
                activeTab === 0 ? contracts :
                activeTab === 1 ? [
                  { name: 'Vanta Digital Retainer',          party: 'Vanta Digital',   status: 'PENDING', nextDue: '2026-04-18' },
                  { name: 'Nova Tech Support Agreement',      party: 'Nova Tech',        status: 'PENDING', nextDue: '2026-04-22' },
                  { name: 'Clearpath Inc Amendment',          party: 'Clearpath Inc',    status: 'PENDING', nextDue: '2026-04-25' },
                  { name: 'Fenix Creative Renewal',           party: 'Fenix Creative',   status: 'PENDING', nextDue: '2026-04-30' },
                  { name: 'BluePrint Agency Update',          party: 'BluePrint Agency', status: 'PENDING', nextDue: '2026-05-02' },
                  { name: 'Meridian Labs Addendum',           party: 'Meridian Labs',    status: 'PENDING', nextDue: '2026-05-08' },
                  { name: 'Apex Media Review',                party: 'Apex Media',       status: 'PENDING', nextDue: '2026-05-10' },
                  { name: 'Groundwork Labs Pending',          party: 'Groundwork Labs',  status: 'PENDING', nextDue: '2026-05-15' },
                  { name: 'Orin Staffing Revision',           party: 'Orin Staffing',    status: 'PENDING', nextDue: '2026-05-18' },
                  { name: 'Crestwood Consulting Review',      party: 'Crestwood',        status: 'PENDING', nextDue: '2026-05-22' },
                ] :
                activeTab === 4 ? [
                  { name: 'Meridian Labs Q2 Services',        party: 'Meridian Labs',    status: 'ACTIVE',  nextDue: '2026-04-15' },
                  { name: 'Orin Staffing Agreement',          party: 'Orin Staffing',    status: 'ACTIVE',  nextDue: '2026-04-18' },
                  { name: 'Clearpath Inc Delivery',           party: 'Clearpath Inc',    status: 'ACTIVE',  nextDue: '2026-04-20' },
                  { name: 'Nova Tech Support',                party: 'Nova Tech',        status: 'ACTIVE',  nextDue: '2026-04-22' },
                  { name: 'Fenix Creative Studio',            party: 'Fenix Creative',   status: 'ACTIVE',  nextDue: '2026-04-24' },
                  { name: 'BluePrint Agency',                 party: 'BluePrint Agency', status: 'ACTIVE',  nextDue: '2026-04-26' },
                  { name: 'Apex Media Partnership',           party: 'Apex Media',       status: 'ACTIVE',  nextDue: '2026-04-28' },
                  { name: 'Groundwork Labs',                  party: 'Groundwork Labs',  status: 'ACTIVE',  nextDue: '2026-04-30' },
                  { name: 'Vanta Digital Retainer',           party: 'Vanta Digital',    status: 'ACTIVE',  nextDue: '2026-05-01' },
                  { name: 'Crestwood Consulting',             party: 'Crestwood',        status: 'ACTIVE',  nextDue: '2026-05-03' },
                ] : [
                  { name: 'Clearpath Inc Delivery SLA',       party: 'Clearpath Inc',    status: 'COMPLETED', nextDue: '—' },
                  { name: 'Orin Staffing Q1',                 party: 'Orin Staffing',    status: 'COMPLETED', nextDue: '—' },
                  { name: 'Nova Tech Phase 1',                party: 'Nova Tech',        status: 'COMPLETED', nextDue: '—' },
                  { name: 'Fenix Creative Q4',                party: 'Fenix Creative',   status: 'COMPLETED', nextDue: '—' },
                  { name: 'BluePrint Agency 2025',            party: 'BluePrint Agency', status: 'COMPLETED', nextDue: '—' },
                  { name: 'Apex Media 2025 Deal',             party: 'Apex Media',       status: 'COMPLETED', nextDue: '—' },
                  { name: 'Groundwork Labs Phase 1',          party: 'Groundwork Labs',  status: 'COMPLETED', nextDue: '—' },
                  { name: 'Meridian Labs Q1',                 party: 'Meridian Labs',    status: 'COMPLETED', nextDue: '—' },
                  { name: 'Vanta Digital 2025',               party: 'Vanta Digital',    status: 'COMPLETED', nextDue: '—' },
                  { name: 'Crestwood Q4 2025',                party: 'Crestwood',        status: 'COMPLETED', nextDue: '—' },
                ]
              return (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 16 }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #E5E7EB' }}>
                        <th style={TH_DARK}>Contract Name</th>
                        <th style={TH_DARK}>Party</th>
                        <th style={TH_DARK}>Status</th>
                        <th style={TH_DARK}>Next Due Date</th>
                        <th style={{ ...TH_DARK, paddingRight: 0 }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, i) => (
                        <tr
                          key={i}
                          style={{
                            borderBottom: '1px solid #E5E7EB',
                            background: hoveredRow === i ? '#E8EDF2' : 'transparent',
                            transition: 'background 0.1s',
                          }}
                          onMouseEnter={() => setHoveredRow(i)}
                          onMouseLeave={() => setHoveredRow(null)}
                        >
                          <td style={{ ...TD_DARK, fontWeight: 500 }}>{row.name}</td>
                          <td style={TD_DARK}>{row.party}</td>
                          <td style={TD_DARK}>
                            <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', ...STATUS_DARK[row.status] }}>
                              {row.status}
                            </span>
                          </td>
                          <td style={{ ...TD_DARK, color: '#9CA3AF' }}>{row.nextDue}</td>
                          <td style={{ ...TD_DARK, paddingRight: 0 }}>
                            <button
                              style={{ fontSize: 12, fontWeight: 500, color: '#374151', background: 'transparent', border: '1px solid #D1D5DB', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = '#E5E7EB' }}
                              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
                            >
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
                    <tr style={{ borderBottom: '1px solid #E5E7EB' }}>
                      <th style={TH_DARK}>Obligation</th>
                      <th style={TH_DARK}>Contract</th>
                      <th style={TH_DARK}>Status</th>
                      <th style={{ ...TH_DARK, paddingRight: 0 }}>Due Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { obligation: 'Monthly Payment — Apr',    contract: 'Meridian Labs Q2',        status: 'ACTIVE', dueDate: '2026-04-10' },
                      { obligation: 'Delivery Milestone 2',     contract: 'Orin Staffing Agreement', status: 'ACTIVE', dueDate: '2026-04-14' },
                      { obligation: 'Quarterly Review',         contract: 'Fenix Creative Studio',   status: 'ACTIVE', dueDate: '2026-04-20' },
                      { obligation: 'Service Delivery Phase 1', contract: 'BluePrint Agency',        status: 'ACTIVE', dueDate: '2026-04-25' },
                      { obligation: 'Payment Installment 3',    contract: 'Nova Tech Support',       status: 'ACTIVE', dueDate: '2026-04-28' },
                      { obligation: 'Milestone Review',         contract: 'Apex Media Partnership',  status: 'ACTIVE', dueDate: '2026-05-01' },
                      { obligation: 'Monthly Retainer Fee',     contract: 'Vanta Digital',           status: 'ACTIVE', dueDate: '2026-05-05' },
                      { obligation: 'Delivery Sign-off',        contract: 'Groundwork Labs',         status: 'ACTIVE', dueDate: '2026-05-08' },
                      { obligation: 'Phase 2 Payment',          contract: 'Clearpath Inc',           status: 'ACTIVE', dueDate: '2026-05-12' },
                      { obligation: 'Final Review',             contract: 'Crestwood Consulting',    status: 'ACTIVE', dueDate: '2026-05-15' },
                    ].map((row, i) => (
                      <tr
                        key={i}
                        style={{
                          borderBottom: '1px solid rgba(255,255,255,0.06)',
                          background: hoveredRow === i ? 'rgba(255,255,255,0.05)' : 'transparent',
                          transition: 'background 0.1s',
                        }}
                        onMouseEnter={() => setHoveredRow(i)}
                        onMouseLeave={() => setHoveredRow(null)}
                      >
                        <td style={{ ...TD_DARK, fontWeight: 500 }}>{row.obligation}</td>
                        <td style={TD_DARK}>{row.contract}</td>
                        <td style={TD_DARK}>
                          <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', ...STATUS_DARK[row.status] }}>
                            {row.status}
                          </span>
                        </td>
                        <td style={{ ...TD_DARK, paddingRight: 0, color: '#9CA3AF' }}>{row.dueDate}</td>
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
                    <tr style={{ borderBottom: '1px solid #E5E7EB' }}>
                      <th style={TH_DARK}>Contract</th>
                      <th style={TH_DARK}>Version</th>
                      <th style={TH_DARK}>Parties</th>
                      <th style={{ ...TH_DARK, paddingRight: 0 }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { contract: 'Meridian Labs Q2',        version: 'v2', parties: 'bonup ↔ Meridian Labs',    status: 'PENDING' },
                      { contract: 'Vanta Digital Retainer',  version: 'v1', parties: 'bonup ↔ Vanta Digital',    status: 'PENDING' },
                      { contract: 'Clearpath Inc SLA',       version: 'v3', parties: 'bonup ↔ Clearpath Inc',    status: 'PENDING' },
                      { contract: 'Nova Tech Agreement',     version: 'v1', parties: 'bonup ↔ Nova Tech',        status: 'PENDING' },
                      { contract: 'Fenix Creative Renewal',  version: 'v2', parties: 'bonup ↔ Fenix Creative',   status: 'PENDING' },
                      { contract: 'BluePrint Agency Update', version: 'v1', parties: 'bonup ↔ BluePrint Agency', status: 'PENDING' },
                      { contract: 'Apex Media Deal',         version: 'v2', parties: 'bonup ↔ Apex Media',       status: 'PENDING' },
                      { contract: 'Groundwork Labs Rev',     version: 'v1', parties: 'bonup ↔ Groundwork Labs',  status: 'PENDING' },
                      { contract: 'Orin Staffing Rev',       version: 'v3', parties: 'bonup ↔ Orin Staffing',    status: 'PENDING' },
                      { contract: 'Crestwood Amendment',     version: 'v1', parties: 'bonup ↔ Crestwood',        status: 'PENDING' },
                    ].map((row, i) => (
                      <tr
                        key={i}
                        style={{
                          borderBottom: '1px solid rgba(255,255,255,0.06)',
                          background: hoveredRow === i ? 'rgba(255,255,255,0.05)' : 'transparent',
                          transition: 'background 0.1s',
                        }}
                        onMouseEnter={() => setHoveredRow(i)}
                        onMouseLeave={() => setHoveredRow(null)}
                      >
                        <td style={{ ...TD_DARK, fontWeight: 500 }}>{row.contract}</td>
                        <td style={{ ...TD_DARK, color: '#9CA3AF', fontFamily: 'monospace' }}>{row.version}</td>
                        <td style={TD_DARK}>{row.parties}</td>
                        <td style={{ ...TD_DARK, paddingRight: 0 }}>
                          <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', ...STATUS_DARK[row.status] }}>
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
        </div>
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
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', height: '100%' }}>
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
                    onClick={openCreateModal}
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
