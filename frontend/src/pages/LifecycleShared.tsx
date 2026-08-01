import type { ReactNode } from 'react'
import { dateOnlyInputValue, dateOnlyPayloadValue, formatDateOnly } from '@/lib/dateOnly'

export type ActionFeedback = { kind: 'success' | 'error'; message: string } | null

export function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString()
}

export function timelineDateLabel(value?: string | null) {
  return formatDateOnly(value, '—')
}

export function formatMoney(amount?: string, currency = 'USD') {
  if (!amount) return '—'
  const parsed = Number(amount)
  if (Number.isNaN(parsed)) return `${amount} ${currency}`
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(parsed)
}

export function humanize(value?: string) {
  if (!value) return '—'
  return value.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

export function toDateInputValue(value?: string | null) {
  return dateOnlyInputValue(value)
}

export function fromDateInputValue(value: string) {
  return dateOnlyPayloadValue(value)
}

export function statusStyle(label: string) {
  if (label === 'In Progress') return { background: '#E0F2FE', color: '#0369A1' }
  if (label === 'Due') return { background: '#FEF3C7', color: '#B45309' }
  if (label === 'Late' || label === 'Missed') return { background: '#FEF2F2', color: '#B91C1C' }
  if (label === 'Paid' || label === 'Performed') return { background: '#ECFDF5', color: '#047857' }
  return { background: '#F8FAFC', color: '#475569' }
}

export function getErrorMessage(error: unknown, fallback: string) {
  const response = (error as { response?: { data?: { error?: string; detail?: string } } })?.response
  return response?.data?.error || response?.data?.detail || fallback
}

export function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div style={{ background: 'white', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 8, padding: 18 }}>
      <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#9CA3AF', margin: 0 }}>{label}</p>
      <p style={{ fontSize: 26, lineHeight: 1.1, fontWeight: 800, color: '#0F1F3D', margin: '8px 0 0' }}>{value}</p>
      {sub && <p style={{ fontSize: 12, color: '#6B7280', margin: '6px 0 0' }}>{sub}</p>}
    </div>
  )
}

export function EmptyStates() {
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {[
        'No timeline to-dos found yet.',
        'Signed agreement records will appear here as they are added.',
        'Timeline records remain planned until performance activity begins.',
      ].map((message) => (
        <div key={message} style={{ border: '1px dashed #CBD5E1', borderRadius: 8, padding: 18, background: '#F8FAFC' }}>
          <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>{message}</p>
        </div>
      ))}
    </div>
  )
}


export function ModalShell({
  title,
  onClose,
  children,
  width = 760,
  eyebrow = 'Timeline action',
}: {
  title: string
  onClose: () => void
  children: ReactNode
  width?: number
  eyebrow?: string
}) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15, 23, 42, 0.45)',
        zIndex: 60,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: width,
          maxHeight: '90vh',
          overflow: 'auto',
          background: '#FFFFFF',
          borderRadius: 12,
          boxShadow: '0 20px 60px rgba(15, 23, 42, 0.3)',
          border: '1px solid rgba(15, 23, 42, 0.08)',
          padding: 20,
        }}
        onClick={(event) => event.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <div>
            <p style={{ margin: 0, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#94A3B8', fontWeight: 700 }}>{eyebrow}</p>
            <h3 style={{ margin: '4px 0 0', fontSize: 20, fontWeight: 800, color: '#0F1F3D' }}>{title}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: '1px solid #CBD5E1', background: '#FFFFFF', color: '#334155', borderRadius: 8, padding: '8px 12px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
          >
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
