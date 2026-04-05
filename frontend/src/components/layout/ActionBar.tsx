const BTN: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  height: 28,
  padding: '0 14px',
  borderRadius: 7,
  fontSize: 12,
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
    </div>
  )
}
