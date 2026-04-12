// src/pages/NewContract.tsx
// Create Contract form — React Hook Form, all fields wired to backend names.

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import api from '@/api/client'
import type { BusinessEntity } from '@/types/entities'

// ── Types ──────────────────────────────────────────────────────────────────────

interface FormValues {
  title: string
  contract_type: string
  language: string
  start_date: string
  end_date: string
  contract_value: string
  currency: string
  description: string
  jurisdiction: string
  governing_law: string
  confidentiality: string
  dispute_resolution: string
  counterparty_name: string
  counterparty_email: string
  // entity selection managed separately via state
}

interface UserResult {
  bon_id: string
  first_name: string
  last_name: string
  email: string
  username: string
}

// ── Constants ──────────────────────────────────────────────────────────────────

const CONTRACT_TYPES = [
  'Service Agreement',
  'NDA / Confidentiality Agreement',
  'Employment Contract',
  'Freelance / Consulting Agreement',
  'Partnership Agreement',
  'Joint Venture Agreement',
  'Lease Agreement',
  'Loan Agreement',
  'Settlement Agreement',
  'Purchase Agreement',
  'Other',
]

const LANGUAGES = ['English', 'Spanish', 'French', 'German', 'Portuguese', 'Chinese', 'Japanese', 'Arabic', 'Other']

const CURRENCIES = [
  'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CNY', 'INR', 'BRL', 'MXN',
  'CHF', 'SEK', 'NOK', 'DKK', 'SGD', 'HKD', 'NZD', 'ZAR', 'AED', 'SAR',
]

const CONFIDENTIALITY_OPTIONS = [
  'Not confidential',
  'Fully confidential',
  'Partially confidential',
  'One-way confidentiality (initiator)',
  'One-way confidentiality (counterparty)',
]

const DISPUTE_OPTIONS = [
  'Negotiation',
  'Mediation',
  'Arbitration',
  'Litigation',
  'Mediation then Arbitration',
]

// ── Design tokens ──────────────────────────────────────────────────────────────

const PAGE_BG = '#ECEEF2'
const NAVY = '#1C2B3A'
const ACCENT = '#F5A623'

const CARD: React.CSSProperties = {
  background: '#ffffff',
  borderRadius: 18,
  border: '1px solid rgba(0,0,0,0.06)',
  padding: '28px 32px',
  marginBottom: 20,
}

const SECTION_TITLE: React.CSSProperties = {
  fontFamily: "'Outfit', sans-serif",
  fontSize: 13,
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: NAVY,
  marginBottom: 20,
  paddingBottom: 12,
  borderBottom: '1px solid #E5E7EB',
}

const LABEL: React.CSSProperties = {
  fontFamily: "'Outfit', sans-serif",
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: '#6B7280',
  display: 'block',
  marginBottom: 6,
}

const INPUT: React.CSSProperties = {
  width: '100%',
  height: 40,
  background: '#F9FAFB',
  border: '1px solid #E5E7EB',
  borderRadius: 8,
  padding: '0 12px',
  fontSize: 13,
  color: NAVY,
  fontFamily: "'Outfit', sans-serif",
  outline: 'none',
  boxSizing: 'border-box',
  transition: 'border-color 0.15s, box-shadow 0.15s',
}

const INPUT_ERROR: React.CSSProperties = {
  ...INPUT,
  borderColor: '#EF4444',
}

const SELECT: React.CSSProperties = {
  ...INPUT,
  cursor: 'pointer',
  appearance: 'none',
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%236B7280' d='M1 1l5 5 5-5'/%3E%3C/svg%3E")`,
  backgroundRepeat: 'no-repeat',
  backgroundPosition: 'right 12px center',
  paddingRight: 32,
}

const TEXTAREA: React.CSSProperties = {
  ...INPUT,
  height: 88,
  padding: '10px 12px',
  resize: 'vertical',
  lineHeight: '1.5',
}

const ERR: React.CSSProperties = {
  fontFamily: "'Outfit', sans-serif",
  fontSize: 11,
  color: '#EF4444',
  marginTop: 4,
}

const ROW2: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: 16,
}

const ROW3: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: '1fr 1fr 1fr',
  gap: 16,
}

function focusIn(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
  e.currentTarget.style.borderColor = NAVY
  e.currentTarget.style.boxShadow = '0 0 0 3px rgba(28,43,58,0.08)'
}
function focusOut(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
  e.currentTarget.style.borderColor = '#E5E7EB'
  e.currentTarget.style.boxShadow = 'none'
}

// ── Field wrapper ──────────────────────────────────────────────────────────────

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={LABEL}>{label}</label>
      {children}
      {error && <span style={ERR}>{error}</span>}
    </div>
  )
}

// ── Contact search ─────────────────────────────────────────────────────────────

function ContactSearch({ onSelect }: { onSelect: (name: string, email: string) => void }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<UserResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const search = useCallback((q: string) => {
    if (!q.trim()) { setResults([]); setOpen(false); return }
    setLoading(true)
    api.get<{ users: UserResult[] }>('/search/', { params: { q } })
      .then(({ data }) => {
        setResults(data.users ?? [])
        setOpen(true)
      })
      .catch(() => setResults([]))
      .finally(() => setLoading(false))
  }, [])

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value
    setQuery(q)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => search(q), 300)
  }

  function handleSelect(u: UserResult) {
    const name = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username
    onSelect(name, u.email)
    setQuery(name)
    setOpen(false)
  }

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [])

  return (
    <div ref={containerRef} style={{ position: 'relative', marginBottom: 16 }}>
      <label style={LABEL}>Search Contacts</label>
      <div style={{ position: 'relative' }}>
        <input
          type="text"
          placeholder="Search by name, email, or BonID…"
          value={query}
          onChange={handleChange}
          onFocus={focusIn}
          onBlur={focusOut}
          style={{ ...INPUT, paddingRight: 36 }}
          autoComplete="off"
        />
        {loading && (
          <span style={{
            position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
            fontSize: 11, color: '#9CA3AF',
          }}>
            …
          </span>
        )}
      </div>
      {open && results.length > 0 && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
          background: '#fff', borderRadius: 10,
          border: '1px solid #E5E7EB',
          boxShadow: '0 8px 24px rgba(0,0,0,0.1)',
          zIndex: 200, overflow: 'hidden',
        }}>
          {results.map((u) => {
            const name = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username
            return (
              <div
                key={u.bon_id || u.email}
                onClick={() => handleSelect(u)}
                style={{
                  padding: '10px 14px',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                  borderBottom: '1px solid #F3F4F6',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#F9FAFB')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <span style={{ fontFamily: "'Outfit', sans-serif", fontSize: 13, fontWeight: 600, color: NAVY }}>
                  {name}
                </span>
                <span style={{ fontFamily: "'Outfit', sans-serif", fontSize: 11, color: '#6B7280' }}>
                  {u.email}
                  {u.bon_id ? <span style={{ marginLeft: 8, color: '#9CA3AF' }}>· {u.bon_id}</span> : null}
                </span>
              </div>
            )
          })}
        </div>
      )}
      {open && results.length === 0 && query.trim() && !loading && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
          background: '#fff', borderRadius: 10,
          border: '1px solid #E5E7EB',
          boxShadow: '0 8px 24px rgba(0,0,0,0.1)',
          zIndex: 200, padding: '12px 14px',
        }}>
          <span style={{ fontFamily: "'Outfit', sans-serif", fontSize: 12, color: '#9CA3AF' }}>
            No users found
          </span>
        </div>
      )}
    </div>
  )
}

// ── Entity picker ──────────────────────────────────────────────────────────────

function EntityPicker({
  value,
  onChange,
}: {
  value: { type: 'personal'; id: null } | { type: 'business'; id: string; name: string }
  onChange: (v: { type: 'personal'; id: null } | { type: 'business'; id: string; name: string }) => void
}) {
  const [entities, setEntities] = useState<BusinessEntity[]>([])

  useEffect(() => {
    api.get<{ results: BusinessEntity[] }>('/entities/')
      .then(({ data }) => setEntities(data.results))
      .catch(() => {})
  }, [])

  return (
    <div>
      <label style={LABEL}>Contracting Party</label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {/* Personal */}
        <button
          type="button"
          onClick={() => onChange({ type: 'personal', id: null })}
          style={{
            height: 36, padding: '0 16px', borderRadius: 8,
            fontFamily: "'Outfit', sans-serif", fontSize: 12, fontWeight: 600,
            cursor: 'pointer', transition: 'all 0.15s',
            border: value.type === 'personal' ? `2px solid ${ACCENT}` : '1px solid #E5E7EB',
            background: value.type === 'personal' ? `rgba(245,166,35,0.08)` : '#F9FAFB',
            color: value.type === 'personal' ? ACCENT : '#6B7280',
          }}
        >
          Personal
        </button>
        {entities.map((e) => {
          const active = value.type === 'business' && value.id === e.id
          return (
            <button
              key={e.id}
              type="button"
              onClick={() => onChange({ type: 'business', id: e.id, name: e.name })}
              style={{
                height: 36, padding: '0 16px', borderRadius: 8,
                fontFamily: "'Outfit', sans-serif", fontSize: 12, fontWeight: 600,
                cursor: 'pointer', transition: 'all 0.15s',
                border: active ? `2px solid ${ACCENT}` : '1px solid #E5E7EB',
                background: active ? `rgba(245,166,35,0.08)` : '#F9FAFB',
                color: active ? ACCENT : '#6B7280',
              }}
            >
              {e.name}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function NewContract() {
  const navigate = useNavigate()

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    defaultValues: {
      title: '',
      contract_type: '',
      language: 'English',
      start_date: '',
      end_date: '',
      contract_value: '',
      currency: 'USD',
      description: '',
      jurisdiction: '',
      governing_law: '',
      confidentiality: 'Not confidential',
      dispute_resolution: 'Negotiation',
      counterparty_name: '',
      counterparty_email: '',
    },
  })

  type EntitySelection =
    | { type: 'personal'; id: null }
    | { type: 'business'; id: string; name: string }

  const [entity, setEntity] = useState<EntitySelection>(() => {
    try {
      const raw = localStorage.getItem('bb_active_entity')
      if (raw) {
        const saved = JSON.parse(raw) as { id: string | null; name: string }
        if (saved.id !== null) return { type: 'business', id: saved.id, name: saved.name }
      }
    } catch {}
    return { type: 'personal', id: null }
  })

  function handleEntityChange(v: EntitySelection) {
    setEntity(v)
    localStorage.setItem('bb_active_entity', JSON.stringify({
      id: v.id,
      name: v.type === 'personal' ? 'Personal' : (v as { type: 'business'; id: string; name: string }).name,
    }))
  }
  const [submitError, setSubmitError] = useState('')

  function handleContactSelect(name: string, email: string) {
    setValue('counterparty_name', name, { shouldValidate: true })
    setValue('counterparty_email', email, { shouldValidate: true })
  }

  const structureTypeFromContractType = (ct: string): string => {
    if (ct === 'Employment Contract') return 'ONGOING'
    if (ct === 'Partnership Agreement' || ct === 'Joint Venture Agreement') return 'COLLABORATIVE'
    if (ct === 'Settlement Agreement') return 'RESOLUTION'
    return 'ONE_TIME'
  }

  async function onSubmit(data: FormValues) {
    setSubmitError('')
    const payload: Record<string, unknown> = {
      title: data.title,
      contract_type: data.contract_type,
      language: data.language,
      start_date: data.start_date || null,
      end_date: data.end_date || null,
      contract_value: data.contract_value ? data.contract_value : null,
      currency: data.currency,
      description: data.description,
      jurisdiction: data.jurisdiction,
      governing_law: data.governing_law,
      confidentiality: data.confidentiality,
      dispute_resolution: data.dispute_resolution,
      counterparty_name: data.counterparty_name,
      counterparty_email: data.counterparty_email || 'pending@bonup.placeholder',
      structure_type: structureTypeFromContractType(data.contract_type),
      entity_type: entity.type,
      status: 'draft',
    }
    if (entity.type === 'business') {
      payload.entity = entity.id
    }

    try {
      const { data: created } = await api.post('/contracts/', payload)
      console.log('[NewContract] full API response:', created)
      // Verify by refetching
      const { data: full } = await api.get(`/contracts/${created.id}/`)
      console.log('[NewContract] verified GET /contracts/:id/ response:', full)
    } catch (err: unknown) {
      const errData = (err as { response?: { data?: unknown } })?.response?.data
      const msg = errData
        ? Object.values(errData as Record<string, unknown>).flat().join(' ')
        : 'Failed to create contract. Please try again.'
      setSubmitError(String(msg))
    }
  }

  return (
    <div style={{ fontFamily: "'Outfit', sans-serif", background: PAGE_BG, minHeight: '100vh', padding: '32px 0' }}>
      <div style={{ maxWidth: 780, margin: '0 auto', padding: '0 20px' }}>

        {/* Page header */}
        <div style={{ marginBottom: 28 }}>
          <h1 style={{
            fontFamily: "'Outfit', sans-serif",
            fontSize: 24, fontWeight: 700, color: NAVY,
            margin: 0, letterSpacing: '-0.01em',
          }}>
            New Contract
          </h1>
          <p style={{ fontFamily: "'Outfit', sans-serif", fontSize: 13, color: '#6B7280', margin: '6px 0 0' }}>
            Fill in the details below. All fields can be edited after creation.
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} noValidate>

          {/* ── Section 1: Basic Details ── */}
          <div style={CARD}>
            <div style={SECTION_TITLE}>Basic Details</div>

            <Field label="Contract Title *" error={errors.title?.message}>
              <input
                {...register('title', { required: 'Title is required' })}
                placeholder="e.g. Lawn Care Service Agreement"
                style={errors.title ? INPUT_ERROR : INPUT}
                onFocus={focusIn}
                onBlur={focusOut}
              />
            </Field>

            <div style={ROW2}>
              <Field label="Contract Type *" error={errors.contract_type?.message}>
                <select
                  {...register('contract_type', { required: 'Contract type is required' })}
                  style={errors.contract_type ? { ...SELECT, borderColor: '#EF4444' } : SELECT}
                  onFocus={focusIn}
                  onBlur={focusOut}
                >
                  <option value="">Select type…</option>
                  {CONTRACT_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </Field>

              <Field label="Language">
                <select
                  {...register('language')}
                  style={SELECT}
                  onFocus={focusIn}
                  onBlur={focusOut}
                >
                  {LANGUAGES.map((l) => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              </Field>
            </div>

            <Field label="Description">
              <textarea
                {...register('description')}
                placeholder="Brief description of what this contract covers…"
                style={TEXTAREA}
                onFocus={focusIn}
                onBlur={focusOut}
              />
            </Field>
          </div>

          {/* ── Section 2: Parties ── */}
          <div style={CARD}>
            <div style={SECTION_TITLE}>Parties</div>

            <div style={{ marginBottom: 20 }}>
              <EntityPicker value={entity} onChange={handleEntityChange} />
            </div>

            <ContactSearch onSelect={handleContactSelect} />

            <div style={ROW2}>
              <Field label="Counterparty Name" error={errors.counterparty_name?.message}>
                <input
                  {...register('counterparty_name')}
                  placeholder="Full name"
                  style={INPUT}
                  onFocus={focusIn}
                  onBlur={focusOut}
                />
              </Field>

              <Field label="Counterparty Email" error={errors.counterparty_email?.message}>
                <input
                  {...register('counterparty_email', {
                    validate: (v) =>
                      !v || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) || 'Enter a valid email',
                  })}
                  type="email"
                  placeholder="email@example.com"
                  style={errors.counterparty_email ? INPUT_ERROR : INPUT}
                  onFocus={focusIn}
                  onBlur={focusOut}
                />
              </Field>
            </div>
          </div>

          {/* ── Section 3: Timeline & Value ── */}
          <div style={CARD}>
            <div style={SECTION_TITLE}>Timeline & Value</div>

            <div style={ROW3}>
              <Field label="Start Date">
                <input
                  {...register('start_date')}
                  type="date"
                  style={INPUT}
                  onFocus={focusIn}
                  onBlur={focusOut}
                />
              </Field>

              <Field label="End Date">
                <input
                  {...register('end_date')}
                  type="date"
                  style={INPUT}
                  onFocus={focusIn}
                  onBlur={focusOut}
                />
              </Field>

              <Field label="Currency">
                <select
                  {...register('currency')}
                  style={SELECT}
                  onFocus={focusIn}
                  onBlur={focusOut}
                >
                  {CURRENCIES.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </Field>
            </div>

            <Field label="Contract Value">
              <div style={{ position: 'relative' }}>
                <span style={{
                  position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
                  fontFamily: "'Outfit', sans-serif", fontSize: 13, color: '#9CA3AF',
                }}>
                  {watch('currency') || 'USD'}
                </span>
                <input
                  {...register('contract_value')}
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  style={{ ...INPUT, paddingLeft: 52 }}
                  onFocus={focusIn}
                  onBlur={focusOut}
                />
              </div>
            </Field>
          </div>

          {/* ── Section 4: Legal Terms ── */}
          <div style={CARD}>
            <div style={SECTION_TITLE}>Legal Terms</div>

            <div style={ROW2}>
              <Field label="Jurisdiction">
                <input
                  {...register('jurisdiction')}
                  placeholder="e.g. New York, USA"
                  style={INPUT}
                  onFocus={focusIn}
                  onBlur={focusOut}
                />
              </Field>

              <Field label="Governing Law">
                <input
                  {...register('governing_law')}
                  placeholder="e.g. Laws of New York State"
                  style={INPUT}
                  onFocus={focusIn}
                  onBlur={focusOut}
                />
              </Field>
            </div>

            <div style={ROW2}>
              <Field label="Confidentiality">
                <select
                  {...register('confidentiality')}
                  style={SELECT}
                  onFocus={focusIn}
                  onBlur={focusOut}
                >
                  {CONFIDENTIALITY_OPTIONS.map((o) => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
              </Field>

              <Field label="Dispute Resolution">
                <select
                  {...register('dispute_resolution')}
                  style={SELECT}
                  onFocus={focusIn}
                  onBlur={focusOut}
                >
                  {DISPUTE_OPTIONS.map((o) => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
              </Field>
            </div>
          </div>

          {/* ── Error banner ── */}
          {submitError && (
            <div style={{
              background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
              borderRadius: 10, padding: '12px 16px', marginBottom: 20,
              fontFamily: "'Outfit', sans-serif", fontSize: 13, color: '#DC2626',
            }}>
              {submitError}
            </div>
          )}

          {/* ── Actions ── */}
          <div style={{
            display: 'flex', justifyContent: 'flex-end', gap: 12,
            paddingBottom: 40,
          }}>
            <button
              type="button"
              onClick={() => navigate('/contracts')}
              style={{
                height: 42, padding: '0 24px', borderRadius: 10,
                fontFamily: "'Outfit', sans-serif", fontSize: 13, fontWeight: 600,
                background: 'white', color: '#6B7280',
                border: '1px solid #E5E7EB', cursor: 'pointer',
                transition: 'all 0.15s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#F9FAFB'
                e.currentTarget.style.color = NAVY
                e.currentTarget.style.borderColor = '#D1D5DB'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'white'
                e.currentTarget.style.color = '#6B7280'
                e.currentTarget.style.borderColor = '#E5E7EB'
              }}
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                height: 42, padding: '0 28px', borderRadius: 10,
                fontFamily: "'Outfit', sans-serif", fontSize: 13, fontWeight: 700,
                background: isSubmitting ? '#D1D5DB' : NAVY,
                color: isSubmitting ? '#9CA3AF' : '#ffffff',
                border: 'none', cursor: isSubmitting ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s',
                display: 'flex', alignItems: 'center', gap: 8,
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting) e.currentTarget.style.background = '#2A3F55'
              }}
              onMouseLeave={(e) => {
                if (!isSubmitting) e.currentTarget.style.background = NAVY
              }}
            >
              {isSubmitting ? 'Creating…' : 'Create Contract'}
            </button>
          </div>

        </form>
      </div>
    </div>
  )
}
