import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api from '@/api/client'

type ContractVersionPayload = {
  content_snapshot?: string
  status?: string
  version_number?: number
}

type ContractDocumentPayload = {
  id: string
  title?: string
  status?: string
  state?: string
  version?: number
  contract_type?: string
  counterparty_name?: string
  counterparty_email?: string
  created_at?: string
  latest_version?: ContractVersionPayload | null
}

type ParsedDocument = {
  html?: string
  text?: string
}

const pageStyle: CSSProperties = {
  minHeight: '100vh',
  background: '#F3F5F8',
  padding: '28px 20px 52px',
  fontFamily: "'Outfit', sans-serif",
}

const shellStyle: CSSProperties = {
  maxWidth: 880,
  margin: '0 auto',
}

const documentStyle: CSSProperties = {
  background: 'white',
  border: '1px solid #E2E8F0',
  boxShadow: '0 18px 45px rgba(15,31,61,0.10)',
  borderRadius: 6,
  padding: '44px 52px',
  minHeight: 720,
}

function formatDate(value?: string) {
  if (!value) return 'Unknown date'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown date'
  return date.toLocaleDateString()
}

function statusLabel(contract: ContractDocumentPayload) {
  if (contract.state === 'prepared') return 'Prepared'
  if (contract.state === 'created') return 'Created'
  if (contract.state === 'drafting') return 'Drafting'
  if (contract.status === 'sent') return 'Sent / Awaiting Signature'
  if (contract.status === 'active') return 'Active'
  if (contract.status === 'completed') return 'Completed'
  if (contract.status === 'archived') return 'Archived'
  return contract.status || contract.state || 'Draft'
}

function extractDocument(snapshot?: string): ParsedDocument | null {
  const raw = (snapshot || '').trim()
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw) as {
      editor_html?: unknown
      clauses?: unknown
      raw_content?: unknown
      summary?: unknown
    }

    if (typeof parsed.editor_html === 'string' && parsed.editor_html.trim()) {
      return { html: parsed.editor_html }
    }

    if (Array.isArray(parsed.clauses)) {
      const text = parsed.clauses
        .map((clause) => {
          if (!clause || typeof clause !== 'object') return ''
          const body = (clause as { body?: unknown }).body
          return typeof body === 'string' ? body : ''
        })
        .filter(Boolean)
        .join('\n\n')
      if (text.trim()) return { text }
    }

    if (typeof parsed.raw_content === 'string' && parsed.raw_content.trim()) return { text: parsed.raw_content }
    if (typeof parsed.summary === 'string' && parsed.summary.trim()) return { text: parsed.summary }
  } catch {
    if (raw.startsWith('<')) return { html: raw }
    return { text: raw }
  }

  return null
}

export default function ContractDocumentView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [contract, setContract] = useState<ContractDocumentPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    let cancelled = false
    setLoading(true)
    api.get<ContractDocumentPayload>(`/contracts/${id}/`)
      .then(({ data }) => {
        if (!cancelled) setContract(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err?.response?.data?.error || 'Contract document could not be loaded.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [id])

  const document = useMemo(() => extractDocument(contract?.latest_version?.content_snapshot), [contract])

  if (loading) {
    return <div style={pageStyle}><div style={shellStyle}>Loading contract document...</div></div>
  }

  if (error || !contract) {
    return (
      <div style={pageStyle}>
        <div style={shellStyle}>
          <button onClick={() => navigate('/dashboard')} style={{ border: 'none', background: 'transparent', color: '#64748B', cursor: 'pointer', padding: 0, marginBottom: 16 }}>Back to dashboard</button>
          <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: 14, color: '#B91C1C', fontSize: 13 }}>
            {error || 'Contract document could not be loaded.'}
          </div>
        </div>
      </div>
    )
  }

  const versionNumber = contract.latest_version?.version_number || contract.version || 1
  const counterparty = contract.counterparty_name || contract.counterparty_email || 'Counterparty not provided'

  return (
    <div style={pageStyle}>
      <div style={shellStyle}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
          <button onClick={() => navigate('/dashboard')} style={{ border: 'none', background: 'transparent', color: '#64748B', cursor: 'pointer', padding: 0, fontSize: 13 }}>
            Back to dashboard
          </button>
          <button onClick={() => navigate(`/contracts/${contract.id}`)} style={{ height: 32, padding: '0 12px', border: '1px solid #CBD5E1', background: 'white', color: '#334155', borderRadius: 7, fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
            Contract Summary
          </button>
        </div>

        <div style={documentStyle}>
          <header style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: 22, marginBottom: 30 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 20, alignItems: 'flex-start' }}>
              <div style={{ minWidth: 0 }}>
                <p style={{ margin: '0 0 7px', fontSize: 11, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 800 }}>
                  Read-only contract document
                </p>
                <h1 style={{ margin: 0, color: '#0F1F3D', fontSize: 26, lineHeight: 1.2, fontWeight: 800 }}>
                  {contract.title || 'Untitled Contract'}
                </h1>
              </div>
              <span style={{ flexShrink: 0, borderRadius: 999, padding: '5px 10px', background: '#F1F5F9', color: '#334155', fontSize: 11, fontWeight: 800 }}>
                {statusLabel(contract)}
              </span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 18px', marginTop: 14, color: '#64748B', fontSize: 12 }}>
              <span>Version {versionNumber}</span>
              <span>{contract.contract_type || 'Contract'}</span>
              <span>Created {formatDate(contract.created_at)}</span>
              <span>{counterparty}</span>
            </div>
          </header>

          {document?.html ? (
            <div
              style={{ color: '#1E293B', fontSize: 14, lineHeight: 1.75 }}
              dangerouslySetInnerHTML={{ __html: document.html }}
            />
          ) : document?.text ? (
            <pre style={{ whiteSpace: 'pre-wrap', margin: 0, color: '#1E293B', fontSize: 14, lineHeight: 1.75, fontFamily: "Georgia, 'Times New Roman', serif" }}>
              {document.text}
            </pre>
          ) : (
            <div style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 22, background: '#F8FAFC', color: '#64748B', fontSize: 13, lineHeight: 1.6 }}>
              No drafted contract content yet. Open editor while this contract is still in draft.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
