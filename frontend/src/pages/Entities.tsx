import { useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import type { BusinessEntity, BusinessType } from '@/types/entities'

// Tier: 'Free Trial' | 'Sol Member' | 'As You Go' | 'Blackboard Basic' | 'Blackboard Pro' | 'Blackboard Business' | 'Blackboard Enterprise'
const USER_TIER = 'Blackboard Business'

const MAX_BY_TIER: Record<string, number> = {
  'Free Trial': 1,
  'Sol Member': 0,
  'As You Go': 1,
  'Blackboard Basic': 0,
  'Blackboard Pro': 1,
  'Blackboard Business': 4,
  'Blackboard Enterprise': 35,
}

const BUSINESS_TYPES: BusinessType[] = [
  'LLC', 'Corporation', 'Sole Proprietor', 'Partnership',
  'Non-Profit', 'Trust', 'S-Corp', 'C-Corp', 'Other',
]

function bizInitials(name: string): string {
  const words = name.trim().split(/\s+/)
  return words.length >= 2
    ? (words[0][0] + words[words.length - 1][0]).toUpperCase()
    : name.substring(0, 2).toUpperCase()
}

const LABEL: React.CSSProperties = {
  fontSize: 11, fontWeight: 500, color: '#4B5563',
  marginBottom: 4, display: 'block',
  textTransform: 'uppercase', letterSpacing: '0.06em',
}

const FIELD: React.CSSProperties = {
  width: '100%', background: 'white',
  border: '1px solid #D1D5DB', borderRadius: 8,
  padding: '8px 12px', fontSize: 13, color: '#374151',
  fontFamily: "'Outfit', sans-serif", outline: 'none',
  marginBottom: 12, boxSizing: 'border-box',
}

function onFF(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
  e.currentTarget.style.borderColor = '#0F1F3D'
  e.currentTarget.style.boxShadow = '0 0 0 2px rgba(15,31,61,0.08)'
}
function onFB(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
  e.currentTarget.style.borderColor = '#D1D5DB'
  e.currentTarget.style.boxShadow = 'none'
}

export default function Entities() {
  const { user } = useAuth()

  const maxAllowed = MAX_BY_TIER[USER_TIER] ?? 0
  const tierAllows = maxAllowed > 0

  const [entities, setEntities] = useState<BusinessEntity[]>([])

  // Slide-in form state
  const [panelOpen, setPanelOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formName, setFormName] = useState('')
  const [formType, setFormType] = useState<BusinessType | ''>('')
  const [formIndustry, setFormIndustry] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formAddress, setFormAddress] = useState('')
  const [formWebsite, setFormWebsite] = useState('')
  const [formFoundedDate, setFormFoundedDate] = useState('')

  const atLimit = entities.length >= maxAllowed

  const firstName = user?.first_name || user?.username || ''
  const lastName = user?.last_name || ''
  const displayName = [firstName, lastName].filter(Boolean).join(' ') || 'You'
  const initials =
    [user?.first_name?.[0], user?.last_name?.[0]].filter(Boolean).join('').toUpperCase() ||
    user?.username?.[0]?.toUpperCase() || '?'
  const bonId = user?.bon_id ?? '—'

  function openAdd() {
    setEditingId(null)
    setFormName('')
    setFormType('')
    setFormIndustry('')
    setFormDescription('')
    setFormAddress('')
    setFormWebsite('')
    setFormFoundedDate('')
    setPanelOpen(true)
  }

  function openEdit(entity: BusinessEntity) {
    setEditingId(entity.id)
    setFormName(entity.name)
    setFormType(entity.business_type)
    setFormIndustry(entity.industry)
    setFormDescription(entity.description)
    setFormAddress(entity.address ?? '')
    setFormWebsite(entity.website ?? '')
    setFormFoundedDate(entity.founded_date ?? '')
    setPanelOpen(true)
  }

  function closePanel() {
    setPanelOpen(false)
    setEditingId(null)
  }

  function handleSave() {
    if (!formName.trim() || !formType) return
    if (editingId) {
      setEntities((prev) =>
        prev.map((e) =>
          e.id === editingId
            ? {
                ...e,
                name: formName,
                business_type: formType as BusinessType,
                industry: formIndustry,
                description: formDescription,
                address: formAddress || null,
                website: formWebsite || null,
                founded_date: formFoundedDate || null,
                updated_at: new Date().toISOString(),
              }
            : e
        )
      )
    } else {
      const newEntity: BusinessEntity = {
        id: crypto.randomUUID(),
        name: formName,
        business_type: formType as BusinessType,
        industry: formIndustry,
        description: formDescription,
        address: formAddress || null,
        website: formWebsite || null,
        founded_date: formFoundedDate || null,
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      setEntities((prev) => [...prev, newEntity])
    }
    closePanel()
  }

  function handleDeactivate(id: string) {
    setEntities((prev) => prev.filter((e) => e.id !== id))
  }

  const pct = maxAllowed > 0 ? Math.min(100, (entities.length / maxAllowed) * 100) : 0

  return (
    <div style={{ maxWidth: 780, margin: '0 auto' }}>

      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>
            My Business Entities
          </h1>
          <p style={{ fontSize: 13, color: '#6B7280', marginTop: 4, marginBottom: 0 }}>
            Manage the entities you contract under
          </p>
        </div>
        <button
          onClick={tierAllows && !atLimit ? openAdd : undefined}
          disabled={!tierAllows || atLimit}
          style={{
            height: 36, padding: '0 18px',
            background: tierAllows && !atLimit ? '#0F1F3D' : '#9CA3AF',
            color: 'white', border: 'none', borderRadius: 8,
            fontSize: 13, fontWeight: 600,
            cursor: tierAllows && !atLimit ? 'pointer' : 'default',
            flexShrink: 0,
          }}
          onMouseEnter={(e) => {
            if (tierAllows && !atLimit) e.currentTarget.style.opacity = '0.85'
          }}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
        >
          + Add Business Entity
        </button>
      </div>

      {/* Tier usage indicator */}
      <div style={{
        background: 'white', borderRadius: 11, padding: '14px 20px',
        border: '1px solid rgba(0,0,0,0.05)', marginBottom: 20,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 12, color: '#374151', fontWeight: 500 }}>
            Your plan allows {maxAllowed} business {maxAllowed === 1 ? 'entity' : 'entities'}
          </span>
          <span style={{ fontSize: 12, color: '#6B7280' }}>
            {entities.length} of {maxAllowed} used
          </span>
        </div>
        <div style={{ height: 4, background: '#E5E7EB', borderRadius: 2 }}>
          <div style={{
            height: '100%', background: '#0F1F3D', borderRadius: 2,
            width: `${pct}%`, transition: 'width 0.3s ease',
          }} />
        </div>
        {!tierAllows && (
          <p style={{ fontSize: 11, color: '#D97706', marginTop: 8 }}>
            Business entities are available on Blackboard Pro ($149/month) and above.
          </p>
        )}
      </div>

      {/* Personal identity card */}
      <div style={{
        background: 'white', borderRadius: 11, padding: 20,
        border: '1px solid rgba(0,0,0,0.05)', marginBottom: 16,
        display: 'flex', alignItems: 'center', gap: 16,
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: '50%',
          background: '#0F1F3D', color: 'white',
          fontSize: 18, fontWeight: 600,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          {initials}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 16, fontWeight: 600, color: '#0F1F3D' }}>{displayName}</span>
            <span style={{
              background: '#E5E7EB', color: '#374151',
              fontSize: 11, padding: '3px 8px', borderRadius: 4,
            }}>Personal Identity</span>
          </div>
          <p style={{ fontSize: 12, color: '#8B5CF6', fontFamily: "'DM Mono', monospace", margin: 0 }}>
            bonID: {bonId}
          </p>
        </div>
        <span style={{
          background: '#D1FAE5', color: '#065F46',
          fontSize: 11, padding: '3px 8px', borderRadius: 4, flexShrink: 0,
        }}>Default</span>
      </div>

      {/* Business entity cards */}
      {entities.map((entity) => (
        <div
          key={entity.id}
          style={{
            background: 'white', borderRadius: 11, padding: 20,
            border: '1px solid rgba(0,0,0,0.05)', marginBottom: 16,
            display: 'flex', alignItems: 'center', gap: 16,
          }}
        >
          <div style={{
            width: 48, height: 48, borderRadius: '50%',
            background: '#1E3A55', color: 'white',
            fontSize: 18, fontWeight: 600,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            {bizInitials(entity.name)}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 16, fontWeight: 600, color: '#0F1F3D' }}>{entity.name}</span>
              <span style={{
                background: '#EFF6FF', color: '#1D4ED8',
                fontSize: 11, padding: '3px 8px', borderRadius: 4,
              }}>{entity.business_type}</span>
              {entity.industry && (
                <span style={{
                  background: '#F3F4F6', color: '#374151',
                  fontSize: 11, padding: '3px 8px', borderRadius: 4,
                }}>{entity.industry}</span>
              )}
            </div>
            {entity.description && (
              <p style={{ fontSize: 12, color: '#6B7280', margin: 0 }}>{entity.description}</p>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
            <button
              onClick={() => openEdit(entity)}
              style={{
                height: 30, padding: '0 14px',
                background: 'transparent', color: '#374151',
                border: '1px solid #D1D5DB', borderRadius: 6,
                fontSize: 12, cursor: 'pointer',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#F9FAFB')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              Edit
            </button>
            <button
              onClick={() => handleDeactivate(entity.id)}
              style={{
                height: 30, padding: '0 14px',
                background: 'transparent', color: '#DC2626',
                border: '1px solid #FECACA', borderRadius: 6,
                fontSize: 12, cursor: 'pointer',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#FFF5F5')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              Deactivate
            </button>
          </div>
        </div>
      ))}

      {/* Empty state — tier allows but no businesses */}
      {entities.length === 0 && tierAllows && (
        <div
          onClick={openAdd}
          style={{
            background: 'white', borderRadius: 11, padding: 20,
            border: '1px dashed #D1D5DB', marginBottom: 16,
            display: 'flex', alignItems: 'center', gap: 12,
            cursor: 'pointer', color: '#6B7280', fontSize: 13,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = '#0F1F3D'
            e.currentTarget.style.color = '#0F1F3D'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = '#D1D5DB'
            e.currentTarget.style.color = '#6B7280'
          }}
        >
          <div style={{
            width: 40, height: 40, borderRadius: '50%',
            background: '#F3F4F6',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18, flexShrink: 0,
          }}>
            +
          </div>
          + Add a Business Entity
        </div>
      )}

      {/* Locked state — tier doesn't allow */}
      {!tierAllows && (
        <div style={{
          background: '#F9FAFB', borderRadius: 11, padding: 20,
          border: '1px solid #E5E7EB', marginBottom: 16,
          display: 'flex', alignItems: 'center', gap: 12,
          color: '#9CA3AF', fontSize: 12,
        }}>
          <span style={{ fontSize: 20 }}>🔒</span>
          Business entities available on Blackboard Pro ($149/month) and above.
        </div>
      )}

      {/* Slide-in form panel */}
      {panelOpen && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 400,
            background: 'rgba(0,0,0,0.3)',
          }}
          onClick={(e) => { if (e.target === e.currentTarget) closePanel() }}
        >
          <div style={{
            position: 'fixed', right: 0, top: 0,
            height: '100vh', width: 400,
            background: 'white',
            boxShadow: '-4px 0 24px rgba(0,0,0,0.1)',
            zIndex: 401,
            display: 'flex', flexDirection: 'column',
            transform: 'translateX(0)',
            transition: 'transform 0.3s ease',
            overflow: 'hidden',
          }}>
            {/* Panel header */}
            <div style={{
              padding: '20px 24px 16px',
              borderBottom: '1px solid #E5E7EB',
              flexShrink: 0,
            }}>
              <p style={{ fontSize: 16, fontWeight: 700, color: '#0F1F3D', margin: 0 }}>
                {editingId ? 'Edit Business Entity' : 'Add Business Entity'}
              </p>
            </div>

            {/* Scrollable form body */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
              {/* Business Name */}
              <label style={LABEL}>Business Name *</label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. Philibert Holdings LLC"
                style={FIELD}
                onFocus={onFF}
                onBlur={onFB}
              />

              {/* Business Type */}
              <label style={LABEL}>Business Type *</label>
              <select
                value={formType}
                onChange={(e) => setFormType(e.target.value as BusinessType)}
                style={FIELD}
                onFocus={onFF}
                onBlur={onFB}
              >
                <option value="">Select type...</option>
                {BUSINESS_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>

              {/* Industry */}
              <label style={LABEL}>Industry</label>
              <input
                type="text"
                value={formIndustry}
                onChange={(e) => setFormIndustry(e.target.value)}
                placeholder="e.g. Technology, Healthcare"
                style={FIELD}
                onFocus={onFF}
                onBlur={onFB}
              />

              {/* Description */}
              <label style={LABEL}>Description</label>
              <div style={{ position: 'relative', marginBottom: 12 }}>
                <textarea
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value.slice(0, 300))}
                  placeholder="One line about your business"
                  rows={2}
                  style={{
                    ...FIELD,
                    resize: 'none',
                    marginBottom: 0,
                    lineHeight: 1.5,
                  }}
                  onFocus={onFF}
                  onBlur={onFB}
                />
                <span style={{
                  position: 'absolute', right: 10, bottom: 6,
                  fontSize: 10, color: formDescription.length >= 280 ? '#D97706' : '#9CA3AF',
                }}>
                  {formDescription.length}/300
                </span>
              </div>

              {/* Address */}
              <label style={LABEL}>Address</label>
              <input
                type="text"
                value={formAddress}
                onChange={(e) => setFormAddress(e.target.value)}
                placeholder="Optional"
                style={FIELD}
                onFocus={onFF}
                onBlur={onFB}
              />

              {/* Website */}
              <label style={LABEL}>Website</label>
              <input
                type="url"
                value={formWebsite}
                onChange={(e) => setFormWebsite(e.target.value)}
                placeholder="https://"
                style={FIELD}
                onFocus={onFF}
                onBlur={onFB}
              />

              {/* Founded Date */}
              <label style={LABEL}>Founded Date</label>
              <input
                type="date"
                value={formFoundedDate}
                onChange={(e) => setFormFoundedDate(e.target.value)}
                style={FIELD}
                onFocus={onFF}
                onBlur={onFB}
              />
            </div>

            {/* Panel footer */}
            <div style={{ padding: '16px 24px', borderTop: '1px solid #E5E7EB', flexShrink: 0 }}>
              <button
                onClick={closePanel}
                style={{
                  width: '100%', height: 36,
                  background: 'transparent', color: '#374151',
                  border: '1px solid #D1D5DB', borderRadius: 8,
                  fontSize: 13, fontWeight: 500, cursor: 'pointer',
                  marginBottom: 8,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#F9FAFB')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={!formName.trim() || !formType}
                style={{
                  width: '100%', height: 40,
                  background: !formName.trim() || !formType ? '#9CA3AF' : '#0F1F3D',
                  color: 'white', border: 'none', borderRadius: 8,
                  fontSize: 14, fontWeight: 600,
                  cursor: !formName.trim() || !formType ? 'default' : 'pointer',
                }}
                onMouseEnter={(e) => {
                  if (formName.trim() && formType) e.currentTarget.style.opacity = '0.85'
                }}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              >
                Save Entity
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
