import { useState, useEffect } from 'react'
import {
  loadContacts,
  addContact,
  deleteContact,
  getContactInitials,
  getContactDisplayName,
  type Contact,
} from '@/lib/contacts'

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

function onFF(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) {
  e.currentTarget.style.borderColor = '#243447'
  e.currentTarget.style.boxShadow = '0 0 0 2px rgba(15,31,61,0.08)'
}
function onFB(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) {
  e.currentTarget.style.borderColor = '#D1D5DB'
  e.currentTarget.style.boxShadow = 'none'
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return '—'
  }
}

export default function Contacts() {
  const [contacts, setContacts] = useState<Contact[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [search, setSearch] = useState('')

  // Form state
  const [fFirst, setFFirst] = useState('')
  const [fLast, setFLast] = useState('')
  const [fBonId, setFBonId] = useState('')
  const [fEmail, setFEmail] = useState('')
  const [fPhone, setFPhone] = useState('')
  const [fNotes, setFNotes] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setContacts(loadContacts())
  }, [])

  function reload() {
    setContacts(loadContacts())
  }

  function openModal() {
    setFFirst(''); setFLast(''); setFBonId('')
    setFEmail(''); setFPhone(''); setFNotes('')
    setModalOpen(true)
  }

  function handleSave() {
    if (!fFirst.trim() && !fLast.trim() && !fBonId.trim()) return
    setSaving(true)
    addContact({
      firstName: fFirst.trim(),
      lastName: fLast.trim(),
      bonId: fBonId.trim(),
      email: fEmail.trim(),
      phone: fPhone.trim(),
      notes: fNotes.trim(),
      lastContracted: null,
    })
    reload()
    setModalOpen(false)
    setSaving(false)
  }

  function handleDelete(id: string) {
    deleteContact(id)
    reload()
  }

  const filtered = contacts.filter((c) => {
    const q = search.trim().toLowerCase()
    if (!q) return true
    return (
      getContactDisplayName(c).toLowerCase().includes(q) ||
      c.bonId.toLowerCase().includes(q) ||
      c.email.toLowerCase().includes(q)
    )
  })

  return (
    <div style={{ padding: '32px 40px', maxWidth: 1000, margin: '0 auto' }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 28 }}>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: '#0F1F3D', margin: 0, marginBottom: 4 }}>
            Contacts
          </h1>
          <p style={{ fontSize: 13, color: '#6B7280', margin: 0 }}>
            People you contract with
          </p>
        </div>
        <button
          onClick={openModal}
          style={{
            height: 36, padding: '0 18px',
            background: '#243447', color: 'white',
            border: 'none', borderRadius: 8,
            fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = '#1a3460')}
          onMouseLeave={(e) => (e.currentTarget.style.background = '#243447')}
        >
          + Add Contact
        </button>
      </div>

      {/* Search */}
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by name, bonID, or email…"
        style={{
          width: '100%', height: 38,
          border: '1px solid #D1D5DB', borderRadius: 8,
          padding: '0 14px', fontSize: 13, outline: 'none',
          marginBottom: 24, boxSizing: 'border-box',
          color: '#374151',
        }}
        onFocus={onFF}
        onBlur={onFB}
      />

      {/* Empty state */}
      {contacts.length === 0 && (
        <div style={{
          textAlign: 'center', padding: '64px 0',
          border: '2px dashed #E5E7EB', borderRadius: 12,
          color: '#9CA3AF',
        }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>👥</div>
          <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 6, color: '#6B7280' }}>
            No contacts yet
          </div>
          <div style={{ fontSize: 13 }}>
            Add someone manually or they'll appear here automatically<br />
            when you add them to a contract.
          </div>
        </div>
      )}

      {/* Contact grid */}
      {filtered.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 16,
        }}>
          {filtered.map((c) => (
            <div
              key={c.id}
              style={{
                background: 'white', borderRadius: 10,
                border: '1px solid #E5E7EB',
                padding: '18px 18px 14px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                display: 'flex', flexDirection: 'column', gap: 0,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)')}
              onMouseLeave={(e) => (e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.05)')}
            >
              {/* Avatar + name row */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: '50%',
                  background: '#243447', color: 'white',
                  fontSize: 15, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {getContactInitials(c)}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 14, fontWeight: 600, color: '#0F1F3D',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {getContactDisplayName(c)}
                  </div>
                  {c.bonId && (
                    <div style={{
                      fontSize: 11, color: '#8B5CF6',
                      fontFamily: "'DM Mono', monospace", marginTop: 1,
                    }}>
                      {c.bonId}
                    </div>
                  )}
                </div>
              </div>

              {/* Details */}
              <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 12 }}>
                {c.email && (
                  <div style={{ marginBottom: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {c.email}
                  </div>
                )}
                {c.phone && <div style={{ marginBottom: 3 }}>{c.phone}</div>}
                <div style={{ color: '#9CA3AF', fontSize: 11 }}>
                  Last contracted: {formatDate(c.lastContracted)}
                </div>
              </div>

              {/* Footer buttons */}
              <div style={{ display: 'flex', gap: 8, marginTop: 'auto' }}>
                <button
                  style={{
                    flex: 1, height: 30, fontSize: 11, fontWeight: 500,
                    border: '1px solid #243447', borderRadius: 6,
                    background: '#243447', color: 'white', cursor: 'pointer',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#1a3460')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '#243447')}
                >
                  Add to Contract
                </button>
                <button
                  onClick={() => handleDelete(c.id)}
                  style={{
                    height: 30, padding: '0 10px', fontSize: 11,
                    border: '1px solid #E5E7EB', borderRadius: 6,
                    background: 'transparent', color: '#9CA3AF', cursor: 'pointer',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#DC2626'; e.currentTarget.style.color = '#DC2626' }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#E5E7EB'; e.currentTarget.style.color = '#9CA3AF' }}
                  title="Remove contact"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {search && filtered.length === 0 && contacts.length > 0 && (
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#9CA3AF', fontSize: 13 }}>
          No contacts match "{search}"
        </div>
      )}

      {/* Add Contact modal */}
      {modalOpen && (
        <div
          onClick={() => setModalOpen(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 600,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 24,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 480, background: 'white', borderRadius: 12,
              padding: 28, boxShadow: '0 8px 40px rgba(0,0,0,0.15)',
            }}
          >
            {/* Modal header */}
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
              <div style={{ flex: 1, fontSize: 16, fontWeight: 700, color: '#0F1F3D' }}>
                Add Contact
              </div>
              <button
                onClick={() => setModalOpen(false)}
                style={{
                  background: 'transparent', border: 'none',
                  color: '#9CA3AF', fontSize: 20, cursor: 'pointer', lineHeight: 1,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#374151')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#9CA3AF')}
              >
                ✕
              </button>
            </div>

            {/* Name row */}
            <div style={{ display: 'flex', gap: 12 }}>
              <div style={{ flex: 1 }}>
                <label style={LABEL}>First Name</label>
                <input type="text" value={fFirst} onChange={(e) => setFFirst(e.target.value)}
                  placeholder="First" style={FIELD} onFocus={onFF} onBlur={onFB} />
              </div>
              <div style={{ flex: 1 }}>
                <label style={LABEL}>Last Name</label>
                <input type="text" value={fLast} onChange={(e) => setFLast(e.target.value)}
                  placeholder="Last" style={FIELD} onFocus={onFF} onBlur={onFB} />
              </div>
            </div>

            <label style={LABEL}>bonID</label>
            <input type="text" value={fBonId} onChange={(e) => setFBonId(e.target.value)}
              placeholder="#BONID" style={FIELD} onFocus={onFF} onBlur={onFB} />

            <label style={LABEL}>Email</label>
            <input type="email" value={fEmail} onChange={(e) => setFEmail(e.target.value)}
              placeholder="email@example.com" style={FIELD} onFocus={onFF} onBlur={onFB} />

            <label style={LABEL}>Phone</label>
            <input type="text" value={fPhone} onChange={(e) => setFPhone(e.target.value)}
              placeholder="+1 555 000 0000" style={FIELD} onFocus={onFF} onBlur={onFB} />

            <label style={LABEL}>Notes</label>
            <textarea
              value={fNotes}
              onChange={(e) => setFNotes(e.target.value)}
              placeholder="Optional notes…"
              rows={3}
              style={{ ...FIELD, resize: 'vertical', lineHeight: 1.5 }}
              onFocus={onFF}
              onBlur={onFB}
            />

            {/* Actions */}
            <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
              <button
                onClick={() => setModalOpen(false)}
                style={{
                  flex: 1, height: 38, fontSize: 13,
                  border: '1px solid #D1D5DB', borderRadius: 8,
                  background: 'transparent', color: '#6B7280', cursor: 'pointer',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#243447')}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#D1D5DB')}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving || (!fFirst.trim() && !fLast.trim() && !fBonId.trim())}
                style={{
                  flex: 2, height: 38, fontSize: 13, fontWeight: 600,
                  border: 'none', borderRadius: 8,
                  background: '#243447', color: 'white', cursor: 'pointer',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#1a3460')}
                onMouseLeave={(e) => (e.currentTarget.style.background = '#243447')}
              >
                Save Contact
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
