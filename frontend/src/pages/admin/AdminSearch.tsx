// frontend/src/pages/admin/AdminSearch.tsx
// Operator user search — real data from GET /api/admin/users/?q=

import { useState } from 'react'
import { AdminTable } from './adminShared'
import api from '@/api/client'

interface AdminUser {
  id: number
  email: string
  first_name: string
  last_name: string
  is_staff: boolean
  date_joined: string
  plan: string | null
  subscription_status: string | null
  business_count: number
}

interface Page {
  count: number
  results: AdminUser[]
}

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  active:          { bg: '#ECFDF5', color: '#065F46' },
  trialing:        { bg: '#EFF6FF', color: '#1D4ED8' },
  per_contract:    { bg: '#F0FDF4', color: '#15803D' },
  past_due:        { bg: '#FEF9C3', color: '#854D0E' },
  cancelled:       { bg: '#FEF2F2', color: '#B91C1C' },
  no_subscription: { bg: '#F9FAFB', color: '#6B7280' },
}

export default function AdminSearch() {
  const [input, setInput] = useState('')
  const [results, setResults] = useState<AdminUser[] | null>(null)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    const q = input.trim()
    if (!q) return
    setLoading(true)
    setError(null)
    api.get<Page>(`/admin/users/?q=${encodeURIComponent(q)}`)
      .then((r) => { setResults(r.data.results); setTotal(r.data.count) })
      .catch(() => setError('Search failed.'))
      .finally(() => setLoading(false))
  }

  return (
    <div className="space-y-4" style={{ maxWidth: 860 }}>
      <p style={{ fontSize: 13, color: '#6B7280' }}>
        Search users by bonID, email, or name.
      </p>

      <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8 }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="bonID, email, or name…"
          autoFocus
          style={{
            flex: 1, maxWidth: 400, padding: '8px 14px', fontSize: 13,
            border: '1px solid #D1D5DB', borderRadius: 7, outline: 'none',
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            padding: '8px 20px', fontSize: 13, fontWeight: 600,
            background: '#243447', color: '#fff', border: 'none',
            borderRadius: 7, cursor: loading ? 'default' : 'pointer',
            opacity: loading || !input.trim() ? 0.5 : 1,
          }}
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {error && <p style={{ fontSize: 13, color: '#B91C1C' }}>{error}</p>}

      {results !== null && (
        <>
          <p style={{ fontSize: 12, color: '#9CA3AF' }}>
            {total === 0 ? 'No results.' : `${total} result${total !== 1 ? 's' : ''}`}
          </p>

          <AdminTable
            loading={false}
            empty={results.length === 0}
            headers={['ID', 'Email', 'Name', 'Plan', 'Status', 'Businesses', 'Staff', 'Joined']}
          >
            {results.map((u) => {
              const st = STATUS_COLORS[u.subscription_status ?? ''] ?? { bg: '#F9FAFB', color: '#6B7280' }
              return (
                <tr key={u.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-xs font-mono text-slate-400">{u.id}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{u.email}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">
                    {[u.first_name, u.last_name].filter(Boolean).join(' ') || '—'}
                  </td>
                  <td className="px-4 py-3 text-xs font-mono text-slate-500">{u.plan || '—'}</td>
                  <td className="px-4 py-3">
                    <span style={{ display: 'inline-block', fontSize: 11, fontWeight: 500, padding: '2px 8px', borderRadius: 99, background: st.bg, color: st.color }}>
                      {u.subscription_status || 'none'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-center text-slate-500">{u.business_count}</td>
                  <td className="px-4 py-3 text-center text-xs text-slate-400">
                    {u.is_staff ? <span style={{ color: '#D97706', fontWeight: 600 }}>Django staff</span> : ''}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    {new Date(u.date_joined).toLocaleDateString()}
                  </td>
                </tr>
              )
            })}
          </AdminTable>
        </>
      )}
    </div>
  )
}
