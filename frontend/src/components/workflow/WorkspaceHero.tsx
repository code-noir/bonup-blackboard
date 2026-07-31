import { type CSSProperties } from 'react'

type WorkspaceHeroSummaryItem = {
  id: string
  label: string
  value: number
  loading?: boolean
  enabled?: boolean
  onClick?: () => void
}

type WorkspaceHeroProps = {
  summaryItems: WorkspaceHeroSummaryItem[]
  onAnalyzeContract: () => void
  onOpenContractCounter: () => void
}

export function PanelQuickAction({ label, tone, disabled = false, onClick }: { label: string; tone: 'green' | 'blue' | 'neutral' | 'warm' | 'light'; disabled?: boolean; onClick?: () => void }) {
  const styles: Record<typeof tone, CSSProperties> = {
    green: { background: '#10B981', border: '1px solid #10B981', color: 'white' },
    blue: { background: '#243447', border: '1px solid #243447', color: 'white' },
    neutral: { background: 'rgba(226,232,240,0.12)', border: '1px solid rgba(226,232,240,0.28)', color: '#E2E8F0' },
    warm: { background: '#243447', border: '1px solid #243447', color: 'white' },
    light: { background: '#374151', border: '1px solid #374151', color: '#F8FAFC' },
  }

  return (
    <button
      type="button"
      disabled={disabled}
      title={disabled ? 'Coming soon' : undefined}
      onClick={onClick}
      style={{
        ...styles[tone],
        width: '100%',
        minHeight: tone === 'green' ? 50 : 56,
        borderRadius: 10,
        padding: '0 18px',
        fontFamily: "'Outfit', ui-sans-serif, system-ui, sans-serif",
        fontSize: 15,
        fontWeight: 500,
        letterSpacing: '0.02em',
        lineHeight: 1.25,
        WebkitFontSmoothing: 'antialiased',
        MozOsxFontSmoothing: 'grayscale',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.72 : 1,
        boxShadow: tone === 'green' ? '0 10px 22px rgba(16,185,129,0.18)' : 'none',
      }}
    >
      {label}
    </button>
  )
}

export default function WorkspaceHero({ summaryItems, onAnalyzeContract, onOpenContractCounter }: WorkspaceHeroProps) {
  const metricColumns = Array.from({ length: 3 }, (_, columnIndex) =>
    summaryItems.filter((_, itemIndex) => itemIndex % 3 === columnIndex),
  )

  return (
    <div style={{ display: 'grid', gap: 56, paddingBottom: 4 }}>
      <section
        aria-label="Workspace empty state"
        style={{
          minHeight: 384,
          border: '1px solid rgba(148,163,184,0.18)',
          borderRadius: 16,
          backgroundColor: '#243447',
          backgroundImage: [
            'radial-gradient(circle at 18% 22%, rgba(16,185,129,0.08) 0, rgba(16,185,129,0.028) 9%, transparent 24%)',
            'radial-gradient(circle at 78% 18%, rgba(96,165,250,0.08) 0, rgba(96,165,250,0.028) 12%, transparent 28%)',
            'radial-gradient(circle at 64% 72%, rgba(255,255,255,0.04) 0, transparent 22%)',
            'linear-gradient(135deg, #243447 0%, #1E3A55 48%, #2E4156 100%)',
          ].join(', '),
          backgroundSize: '100% 100%, 100% 100%, 100% 100%, 100% 100%',
          backgroundPosition: 'center, center, center, center',
          boxShadow: 'inset 0 0 70px rgba(15,23,42,0.38), 0 12px 32px rgba(15,23,42,0.08)',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundImage: [
              'radial-gradient(circle, rgba(255,255,255,0.14) 0 1px, transparent 1.8px)',
              'radial-gradient(circle, rgba(125,211,252,0.11) 0 1px, transparent 1.6px)',
            ].join(', '),
            backgroundSize: '68px 68px, 118px 118px',
            backgroundPosition: '8px 10px, 28px 32px',
            WebkitMaskImage: 'linear-gradient(180deg, #000 0%, rgba(0,0,0,0.66) 30%, rgba(0,0,0,0.12) 48%, transparent 66%)',
            maskImage: 'linear-gradient(180deg, #000 0%, rgba(0,0,0,0.66) 30%, rgba(0,0,0,0.12) 48%, transparent 66%)',
            pointerEvents: 'none',
          }}
        />
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(180deg, rgba(255,255,255,0.045), transparent 28%, rgba(36,52,71,0.18))',
            pointerEvents: 'none',
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            width: 180,
            height: 180,
            transform: 'translate(-50%, -50%)',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(16,185,129,0.04), transparent 64%)',
            filter: 'blur(6px)',
            pointerEvents: 'none',
          }}
        />
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
            userSelect: 'none',
          }}
        >
          <div style={{ textAlign: 'center', transform: 'translateY(-6%)' }}>
            <p style={{ margin: 0, color: 'rgba(255,255,255,0.05)', fontSize: 'clamp(48px, 8vw, 104px)', fontWeight: 900, lineHeight: 0.95, letterSpacing: 0 }}>
              Blackbòd
            </p>
            <p style={{ margin: '20px 0 0', color: 'rgba(226,232,240,0.70)', fontSize: 15, fontWeight: 500, letterSpacing: '0.2em', lineHeight: 1.35, textTransform: 'uppercase' }}>
              AGREEMENT OPERATIONS CENTER
            </p>
            {summaryItems.length > 0 && (
              <dl style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', columnGap: 72, margin: '38px auto 0', width: '100%', maxWidth: 1280, padding: '0 56px', boxSizing: 'border-box', color: 'rgba(226,232,240,0.78)', maxHeight: 152, overflowY: 'auto', pointerEvents: 'auto' }}>
                {metricColumns.map((column, columnIndex) => (
                  <div key={columnIndex} style={{ display: 'grid', gap: 14, minWidth: 0 }}>
                    {column.filter((item): item is WorkspaceHeroSummaryItem => Boolean(item)).map((item) => (
                      <button key={item.id} type="button" disabled={item.enabled === false} onClick={item.onClick} style={{ display: 'flex', alignItems: 'baseline', gap: 12, minWidth: 0, border: 'none', background: 'transparent', padding: 0, textAlign: 'left', cursor: item.enabled === false ? 'default' : 'pointer', fontFamily: 'inherit' }}>
                        <dd style={{ margin: 0, color: item.enabled === false ? 'rgba(248,250,252,0.48)' : 'rgba(248,250,252,0.9)', fontSize: 16, fontWeight: 600, fontVariantNumeric: 'tabular-nums', lineHeight: 1, textAlign: 'right', flex: '0 0 28px' }}>{item.loading ? '-' : item.value}</dd>
                        <dt style={{ margin: 0, color: item.enabled === false ? 'rgba(196,154,95,0.42)' : 'rgba(196,154,95,0.78)', fontSize: 15, fontWeight: 400, letterSpacing: '0.01em', lineHeight: 1.35, textAlign: 'left', whiteSpace: 'nowrap' }}>{item.label}</dt>
                      </button>
                    ))}
                  </div>
                ))}
              </dl>
            )}
          </div>
        </div>
      </section>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 18, width: '100%', maxWidth: 1010, margin: '0 auto', padding: '0 clamp(0px, 8vw, 90px)', boxSizing: 'border-box', zIndex: 1 }}>
        <PanelQuickAction label="Analyze Agreement" tone="blue" onClick={onAnalyzeContract} />
        <PanelQuickAction label="Agreement Counter" tone="warm" onClick={onOpenContractCounter} />
        <PanelQuickAction label="Invite a Friend" tone="light" disabled />
      </div>
    </div>
  )
}
