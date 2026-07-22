import { useState, useEffect, useRef } from 'react'

const SLOGANS = [
  'Keeping the world together through clear contracting',
  'The #1 peer-to-peer contract platform',
]

type Ad = { title: string; sub: string }

const EXTERNAL_ADS: Ad[] = [
  { title: 'Advertise Here',    sub: 'Reach the bonUP network'    },
  { title: 'Partner Spotlight', sub: 'Coming soon'                },
  { title: 'Your Brand',        sub: 'Contact us to get started'  },
  { title: 'bonUP Partners',    sub: 'Growing every day'          },
]

const INTERNAL_ADS: Ad[] = [
  { title: 'bonUP Pro',        sub: 'Upgrade your experience today' },
  { title: 'bonUP Templates',  sub: 'Start any contract in seconds' },
  { title: 'bonUP Sessions',   sub: 'Go live with your partner'     },
  { title: 'bonUP Sol',        sub: 'Manage payments seamlessly'    },
]

function AdBanner({
  ads,
  dotColor,
  borderColor,
  accentBorderColor,
  maskBg,
  startDelayMs = 0,
}: {
  ads: Ad[]
  dotColor: string
  borderColor: string
  accentBorderColor: string
  maskBg: string
  startDelayMs?: number
}) {
  const [index, setIndex] = useState(0)
  const [started, setStarted] = useState(startDelayMs === 0)

  useEffect(() => {
    if (startDelayMs === 0) return
    const t = setTimeout(() => setStarted(true), startDelayMs)
    return () => clearTimeout(t)
  }, [startDelayMs])

  const ad = ads[index]

  return (
    <div
      style={{
        position: 'relative',
        width: 230,
        height: 44,
        borderRadius: 8,
        overflow: 'hidden',
        flexShrink: 0,
        background: 'rgba(0,0,0,0.18)',
        border: `1px solid ${borderColor}`,
        borderLeft: `3px solid ${accentBorderColor}`,
      }}
    >
      {/* Fixed: dot + title + divider — overlays sliding sub text */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: 10,
          transform: 'translateY(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          whiteSpace: 'nowrap',
          zIndex: 2,
          background: maskBg,
          paddingRight: 8,
        }}
      >
        <div style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: dotColor, flexShrink: 0 }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: '#ffffff' }}>{ad.title}</span>
        <span style={{ color: 'rgba(255,255,255,0.15)', fontSize: 12 }}>·</span>
      </div>

      {/* Sliding subcontent */}
      {started && (
        <span
          key={index}
          onAnimationEnd={() => setIndex((i) => (i + 1) % ads.length)}
          style={{
            position: 'absolute',
            top: '50%',
            left: 0,
            whiteSpace: 'nowrap',
            fontSize: 11,
            fontWeight: 300,
            color: 'rgba(255,255,255,0.5)',
            zIndex: 1,
            animation: 'bonup-sub-slide 12s linear forwards',
          }}
        >
          {ad.sub}
        </span>
      )}
    </div>
  )
}

export default function TopBar() {
  const [sloganIdx, setSloganIdx] = useState(0)
  const [visible, setVisible] = useState(true)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('bb_topbar_collapsed') === 'true')
  const [isCompact, setIsCompact] = useState(false)
  const [isNarrow, setIsNarrow] = useState(false)

  useEffect(() => {
    const compactQuery = window.matchMedia('(max-width: 1100px)')
    const narrowQuery = window.matchMedia('(max-width: 900px)')
    const update = () => {
      setIsCompact(compactQuery.matches)
      setIsNarrow(narrowQuery.matches)
    }
    update()
    compactQuery.addEventListener('change', update)
    narrowQuery.addEventListener('change', update)
    return () => {
      compactQuery.removeEventListener('change', update)
      narrowQuery.removeEventListener('change', update)
    }
  }, [])

  useEffect(() => {
    // Cycle: 10s visible → 3s fade out → swap text → 3s fade in → 10s visible → ...
    timerRef.current = setTimeout(function cycle() {
      setVisible(false)                       // start 3s fade out
      setTimeout(() => {
        setSloganIdx((i) => (i + 1) % SLOGANS.length)
        setVisible(true)                      // start 3s fade in
        timerRef.current = setTimeout(cycle, 13000) // 3s fade-in + 10s hold
      }, 3000)                                // wait for fade out to complete
    }, 10000)                                 // initial 10s hold
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [])

  return (
    <div
      className="app-topbar fixed right-0 z-40 flex h-[64px] items-center px-5"
      style={{
        top: 0,
        left: 'var(--sidebar-w, 216px)',
        background: '#243447',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
      }}
    >
      {!isNarrow && <>
      {/* Left — External ad banner */}
      <AdBanner
        ads={EXTERNAL_ADS}
        dotColor="rgba(255,255,255,0.55)"
        borderColor="rgba(255,255,255,0.12)"
        accentBorderColor="rgba(255,255,255,0.38)"
        maskBg="rgba(22,33,44,0.97)"
        startDelayMs={0}
      />
      </>}

      {/* Center — brand, single horizontal line */}
      <div className="flex flex-1 items-center justify-center gap-2" style={{ minWidth: 0, whiteSpace: 'nowrap' }}>
        <span style={{ fontSize: 14, fontWeight: 600 }}>
          <span style={{ color: 'rgba(255,255,255,0.5)' }}>bon</span>
          <span style={{ color: '#F5A623' }}>UP</span>
        </span>
        <span style={{ color: 'rgba(255,255,255,0.2)', fontSize: 14 }}>·</span>
        <span style={{ fontSize: 18, fontWeight: 800, color: '#ffffff' }}>Blackboard</span>
        {/* Teal dot */}
        {!isCompact && <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#2DD4BF', flexShrink: 0, margin: '0 10px' }} />}
        {!isCompact && <span
          style={{
            display: 'inline-block',
            minWidth: 390,
            fontSize: 13,
            fontWeight: 400,
            fontStyle: 'italic',
            color: 'rgba(255,255,255,0.68)',
            opacity: visible ? 1 : 0,
            transition: 'opacity 3s ease',
            whiteSpace: 'nowrap',
          }}
        >
          {SLOGANS[sloganIdx]}
        </span>}
      </div>

      {!isNarrow && <>
      {/* Right — Internal ad banner */}
      <AdBanner
        ads={INTERNAL_ADS}
        dotColor="#F5A623"
        borderColor="rgba(245,166,35,0.28)"
        accentBorderColor="#F5A623"
        maskBg="rgba(22,33,44,0.97)"
        startDelayMs={6000}
      />
      </>}

      {/* Collapse toggle — gold bee */}
      <button
        onClick={() => {
          const next = !collapsed
          setCollapsed(next)
          localStorage.setItem('bb_topbar_collapsed', String(next))
          window.dispatchEvent(new CustomEvent('topbar-collapse', { detail: next }))
        }}
        title={collapsed ? 'Show header bars' : 'Hide header bars'}
        style={{
          marginLeft: 12, flexShrink: 0,
          background: collapsed ? 'rgba(245,166,35,0.15)' : 'transparent',
          border: `1px solid ${collapsed ? 'rgba(245,166,35,0.5)' : 'rgba(255,255,255,0.2)'}`,
          borderRadius: 6, fontSize: 15, padding: '2px 8px',
          cursor: 'pointer', lineHeight: 1,
          transition: 'background 0.15s, border-color 0.15s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(245,166,35,0.2)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = collapsed ? 'rgba(245,166,35,0.15)' : 'transparent')}
      >
        🐝
      </button>
    </div>
  )
}
