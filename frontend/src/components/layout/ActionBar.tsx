const BTN: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  height: 28,
  padding: '0 10px',
  borderRadius: 7,
  fontSize: 11,
  fontWeight: 500,
  fontFamily: "'Outfit', sans-serif",
  color: 'rgba(255,255,255,0.58)',
  background: 'transparent',
  border: '1px solid rgba(255,255,255,0.12)',
  cursor: 'pointer',
  whiteSpace: 'nowrap' as const,
  transition: 'background 0.15s, color 0.15s',
}

function GhostBtn({ label }: { label: string }) {
  return (
    <button
      style={BTN}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
        e.currentTarget.style.color = '#ffffff'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.color = 'rgba(255,255,255,0.58)'
      }}
    >
      {label}
    </button>
  )
}

export default function ActionBar() {
  return (
    <div
      className="fixed right-0 z-40 flex h-[44px] items-center gap-2 px-5"
      style={{ top: 114, left: 216, background: '#132030' }}
    >
      <GhostBtn label="▶  Start Live Session" />
      <GhostBtn label="+ New Contract" />
      <GhostBtn label="⊟ Browse Templates" />
      <GhostBtn label="⌕ Find a User" />
      <GhostBtn label="⚡ Negotiation Prep" />
      <GhostBtn label="✓ My Obligations" />
      <GhostBtn label="◎ Sol Balance" />
      <GhostBtn label="✦ Ask AI" />
      <GhostBtn label="🌐 Language" />
      <GhostBtn label="+ Contact" />

      {/* Spacer pushes PBVD to far right */}
      <div style={{ flex: 1 }} />

      <button
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          height: 26,
          padding: '0 12px',
          borderRadius: 7,
          fontSize: 11,
          fontWeight: 600,
          fontFamily: "'Outfit', sans-serif",
          color: '#0F2830',
          background: '#2DD4BF',
          border: 'none',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          transition: 'opacity 0.15s',
          flexShrink: 0,
        }}
        onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
        onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
      >
        PBVD
      </button>
    </div>
  )
}
