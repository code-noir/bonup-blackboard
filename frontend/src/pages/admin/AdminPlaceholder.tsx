// frontend/src/pages/admin/AdminPlaceholder.tsx
//
// Truthful placeholder for operator sections that have no admin-level API yet.
// Shows the section name, what backend endpoint exists (if any), and what
// a full implementation would display.

interface AdminPlaceholderProps {
  section: string
  apiNote?: string
  detail?: string
}

export default function AdminPlaceholder({ section, apiNote, detail }: AdminPlaceholderProps) {
  return (
    <div style={{
      background: '#fff',
      borderRadius: 11,
      border: '1px solid rgba(0,0,0,0.07)',
      padding: '48px 40px',
      maxWidth: 560,
    }}>
      <p style={{
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        color: '#9CA3AF',
        margin: '0 0 12px',
      }}>
        Operator Console
      </p>
      <h2 style={{ fontSize: 20, fontWeight: 700, color: '#0F1F3D', margin: '0 0 8px' }}>
        {section}
      </h2>
      <p style={{ fontSize: 13, color: '#6B7280', margin: '0 0 20px', lineHeight: 1.6 }}>
        Operator-level view for this section is not wired yet.
        {detail && ` ${detail}`}
      </p>
      {apiNote && (
        <div style={{
          background: '#F9FAFB',
          border: '1px solid #E5E7EB',
          borderRadius: 7,
          padding: '10px 14px',
          fontFamily: 'monospace',
          fontSize: 12,
          color: '#374151',
        }}>
          <span style={{ color: '#9CA3AF', marginRight: 8 }}>Backend API:</span>
          {apiNote}
        </div>
      )}
    </div>
  )
}
