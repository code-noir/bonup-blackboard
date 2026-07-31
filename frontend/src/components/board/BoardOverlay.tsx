export type BoardOverlayItem = {
  id: string
  title: string
  detail?: string
  meta?: string
}

type BoardOverlayProps = {
  title: string
  subtitle?: string
  items: BoardOverlayItem[]
  loading: boolean
  empty: string
  onClose: () => void
  onSelect: (item: BoardOverlayItem) => void
}

export default function BoardOverlay({
  title,
  subtitle,
  items,
  loading,
  empty,
  onClose,
  onSelect,
}: BoardOverlayProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background: 'rgba(15,23,42,0.48)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 18,
      }}
      onMouseDown={onClose}
    >
      <section
        style={{
          width: 'min(680px, 100%)',
          maxHeight: 'min(720px, calc(100vh - 36px))',
          background: 'white',
          border: '1px solid rgba(15,31,61,0.12)',
          borderRadius: 12,
          boxShadow: '0 24px 70px rgba(15,23,42,0.24)',
          overflow: 'hidden',
          display: 'grid',
          gridTemplateRows: 'auto minmax(0,1fr)',
        }}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 14, borderBottom: '1px solid #E5E7EB', padding: '16px 18px' }}>
          <div style={{ minWidth: 0 }}>
            <h2 style={{ margin: 0, color: '#0F1F3D', fontSize: 18, fontWeight: 800, lineHeight: 1.25 }}>{title}</h2>
            {subtitle && <p style={{ margin: '6px 0 0', color: '#64748B', fontSize: 13, lineHeight: 1.45 }}>{subtitle}</p>}
          </div>
          <button type="button" onClick={onClose} style={{ flexShrink: 0, border: '1px solid #CBD5E1', borderRadius: 8, background: 'white', color: '#334155', height: 32, padding: '0 11px', fontSize: 12, fontWeight: 800, cursor: 'pointer' }}>
            Close
          </button>
        </header>
        <div style={{ overflowY: 'auto', padding: 8 }}>
          {loading ? (
            <p style={{ margin: 0, padding: 12, color: '#64748B', fontSize: 13 }}>Loading...</p>
          ) : items.length === 0 ? (
            <p style={{ margin: 0, padding: 12, color: '#94A3B8', fontSize: 13 }}>{empty}</p>
          ) : (
            <div style={{ display: 'grid' }}>
              {items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelect(item)}
                  style={{
                    border: 'none',
                    borderBottom: '1px solid #E5E7EB',
                    background: 'transparent',
                    padding: '12px 10px',
                    textAlign: 'left',
                    cursor: 'pointer',
                  }}
                >
                  <span style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'baseline' }}>
                    <span style={{ minWidth: 0, color: '#0F1F3D', fontSize: 14, fontWeight: 700, lineHeight: 1.35, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.title}</span>
                    {item.meta && <span style={{ flexShrink: 0, color: '#94A3B8', fontSize: 12, fontWeight: 600 }}>{item.meta}</span>}
                  </span>
                  {item.detail && <span style={{ display: 'block', marginTop: 5, color: '#64748B', fontSize: 12, lineHeight: 1.45 }}>{item.detail}</span>}
                </button>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
