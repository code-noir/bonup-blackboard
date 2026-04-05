import { useState, useEffect } from 'react'

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
  return (
    <div
      className="fixed right-0 z-40 flex h-[64px] items-center px-5"
      style={{
        top: 0,
        left: 216,
        background: '#1C2B3A',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
      }}
    >
      {/* Left — External ad banner */}
      <AdBanner
        ads={EXTERNAL_ADS}
        dotColor="rgba(255,255,255,0.55)"
        borderColor="rgba(255,255,255,0.12)"
        accentBorderColor="rgba(255,255,255,0.38)"
        maskBg="rgba(22,33,44,0.97)"
        startDelayMs={0}
      />

      {/* Center — brand */}
      <div className="flex flex-1 flex-col items-center justify-center">
        <div style={{
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: '0.22em',
          textTransform: 'uppercase',
          marginBottom: 2,
        }}>
          <span style={{ color: 'rgba(255,255,255,0.42)' }}>bon</span>
          <span style={{ color: '#F5A623' }}>UP</span>
        </div>
        <div style={{
          fontSize: 22,
          fontWeight: 800,
          letterSpacing: '-0.02em',
          color: '#ffffff',
          lineHeight: 1,
          marginBottom: 3,
        }}>
          Blackboard
        </div>
        <div style={{
          fontSize: 11,
          fontWeight: 400,
          fontStyle: 'italic',
          color: 'rgba(255,255,255,0.68)',
          whiteSpace: 'nowrap',
        }}>
          Keeping the world together through clear contracting
        </div>
      </div>

      {/* Right — Internal ad banner */}
      <AdBanner
        ads={INTERNAL_ADS}
        dotColor="#F5A623"
        borderColor="rgba(245,166,35,0.28)"
        accentBorderColor="#F5A623"
        maskBg="rgba(22,33,44,0.97)"
        startDelayMs={6000}
      />
    </div>
  )
}
