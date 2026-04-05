import { useState, useEffect } from 'react'

// ─── Ad banner data & component ──────────────────────────────────────────────

type Ad = { title: string; sub: string }

const BONUP_ADS: Ad[] = [
  { title: 'bonUP Pro',        sub: 'Upgrade your experience today'  },
  { title: 'bonUP Templates',  sub: 'Start any contract in seconds'  },
  { title: 'bonUP Sessions',   sub: 'Go live with your partner'      },
  { title: 'bonUP Sol',        sub: 'Manage payments seamlessly'     },
]

const PARTNER_ADS: Ad[] = [
  { title: 'Advertise Here',    sub: 'Reach the bonUP network'      },
  { title: 'Partner Spotlight', sub: 'Coming soon'                  },
  { title: 'Your Brand',        sub: 'Contact us to get started'    },
  { title: 'bonUP Partners',    sub: 'Growing every day'            },
]

function AdBanner({
  ads,
  dotColor,
  accentBorder,
  borderColor,
  startDelayMs = 0,
}: {
  ads: Ad[]
  dotColor: string
  accentBorder: string
  borderColor: string
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
        width: 228,
        height: 32,
        borderRadius: 7,
        overflow: 'hidden',
        flexShrink: 0,
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${borderColor}`,
        borderLeft: `2px solid ${accentBorder}`,
      }}
    >
      {/* Fixed: dot + title + divider — sits above sliding text */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: 9,
          transform: 'translateY(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          whiteSpace: 'nowrap',
          zIndex: 2,
          background: 'rgba(9,17,31,0.92)',
          paddingRight: 8,
        }}
      >
        <div style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: dotColor, flexShrink: 0 }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: '#ffffff', letterSpacing: '0.005em' }}>
          {ad.title}
        </span>
        <span style={{ color: 'rgba(255,255,255,0.12)', fontSize: 12 }}>·</span>
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
            color: 'rgba(255,255,255,0.38)',
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

// ─── TopBar ───────────────────────────────────────────────────────────────────

export default function TopBar() {
  return (
    <div
      className="fixed right-0 z-40 flex h-[50px] items-center px-5"
      style={{
        top: 0,
        left: 216,
        background: '#09111F',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}
    >
      {/* Left — branding + slogan */}
      <div className="flex items-baseline gap-3 shrink-0">
        <div className="flex items-baseline gap-1">
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.18em', textTransform: 'uppercase' }}>
            <span style={{ color: 'rgba(255,255,255,0.35)' }}>bon</span>
            <span style={{ color: 'rgba(245,166,35,0.5)' }}>UP</span>
          </span>
          <span
            style={{
              fontSize: 19,
              fontWeight: 800,
              color: '#ffffff',
              letterSpacing: '-0.01em',
              textShadow: '0 0 1px #fff, 0 0 6px rgba(255,255,255,0.35)',
              lineHeight: 1,
            }}
          >
            Blackboard
          </span>
        </div>
        <span
          style={{
            fontSize: 11,
            fontWeight: 300,
            fontStyle: 'italic',
            color: 'rgba(255,255,255,0.2)',
            whiteSpace: 'nowrap',
          }}
        >
          Keeping the world together through clear contracting
        </span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Right — ad banners */}
      <div className="flex items-center gap-3">
        <AdBanner
          ads={BONUP_ADS}
          dotColor="#F5A623"
          accentBorder="#F5A623"
          borderColor="rgba(245,166,35,0.18)"
          startDelayMs={0}
        />
        <AdBanner
          ads={PARTNER_ADS}
          dotColor="#8B5CF6"
          accentBorder="#8B5CF6"
          borderColor="rgba(139,92,246,0.18)"
          startDelayMs={6000}
        />
      </div>
    </div>
  )
}
