const ghostStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  height: 28,
  padding: '0 14px',
  borderRadius: 7,
  fontSize: 12,
  fontWeight: 500,
  fontFamily: "'Outfit', sans-serif",
  color: 'rgba(255,255,255,0.45)',
  border: '1px solid rgba(255,255,255,0.09)',
  background: 'transparent',
  cursor: 'pointer',
  whiteSpace: 'nowrap' as const,
  transition: 'background 0.15s, color 0.15s',
}

function GhostBtn({ label, onMouseEnter, onMouseLeave }: { label: string; onMouseEnter: React.MouseEventHandler; onMouseLeave: React.MouseEventHandler }) {
  return (
    <button
      style={ghostStyle}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {label}
    </button>
  )
}

export default function ActionBar() {
  const hoverIn: React.MouseEventHandler<HTMLButtonElement> = (e) => {
    e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
    e.currentTarget.style.color = 'rgba(255,255,255,0.78)'
  }
  const hoverOut: React.MouseEventHandler<HTMLButtonElement> = (e) => {
    e.currentTarget.style.background = 'transparent'
    e.currentTarget.style.color = 'rgba(255,255,255,0.45)'
  }

  return (
    <div
      className="fixed right-0 z-40 flex h-[44px] items-center gap-2 px-5"
      style={{
        top: 100,
        left: 216,
        background: '#0B1726',
      }}
    >
      {/* Primary action */}
      <button
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          height: 28,
          padding: '0 14px',
          borderRadius: 7,
          fontSize: 12,
          fontWeight: 500,
          fontFamily: "'Outfit', sans-serif",
          color: '#ffffff',
          background: '#8B5CF6',
          border: 'none',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = '#7C3AED')}
        onMouseLeave={(e) => (e.currentTarget.style.background = '#8B5CF6')}
      >
        ▶&nbsp; Start Live Session
      </button>

      <GhostBtn label="+ New Contract"      onMouseEnter={hoverIn} onMouseLeave={hoverOut} />
      <GhostBtn label="⊟ Browse Templates"  onMouseEnter={hoverIn} onMouseLeave={hoverOut} />
      <GhostBtn label="⌕ Find a User"       onMouseEnter={hoverIn} onMouseLeave={hoverOut} />
    </div>
  )
}
