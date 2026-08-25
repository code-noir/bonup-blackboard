import { useState, useEffect } from 'react'

type Ad = { title: string; sub: string }

const BONUP_ADS: Ad[] = [
  { title: 'bonUP Pro',        sub: 'Upgrade your experience today'  },
  { title: 'bonUP Templates',  sub: 'Start any contract in seconds'  },
  { title: 'bonUP Sessions',   sub: 'Go live with your partner'      },
  { title: 'bonUP Workspace',  sub: 'Track agreement work clearly'   },
]

const PARTNER_ADS: Ad[] = [
  { title: 'Advertise Here',    sub: 'Reach the bonUP network'      },
  { title: 'Partner Spotlight', sub: 'Coming soon'                  },
  { title: 'Your Brand',        sub: 'Contact us to get started'    },
  { title: 'bonUP Partners',    sub: 'Growing every day'            },
]

// Total cycle per ad = 12s slide. Right banner offset by 6s.

function AdSlot({
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
        width: 300,
        height: 34,
        overflow: 'hidden',
        borderRadius: 8,
        background: 'rgba(15,31,61,0.9)',
        border: `1px solid ${borderColor}`,
        borderLeft: `2px solid ${accentBorder}`,
        flexShrink: 0,
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
          gap: 6,
          whiteSpace: 'nowrap',
          zIndex: 2,
          // Background mask so sub text disappears under the title
          background: 'rgba(15,31,61,0.9)',
          paddingRight: 8,
        }}
      >
        <div
          style={{
            width: 5,
            height: 5,
            borderRadius: '50%',
            backgroundColor: dotColor,
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: 11, fontWeight: 600, color: '#ffffff', letterSpacing: '0.01em' }}>
          {ad.title}
        </span>
        <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 11 }}>·</span>
      </div>

      {/* Sliding sub text */}
      {started && (
        <span
          key={index}
          onAnimationEnd={() => setIndex((i) => (i + 1) % ads.length)}
          style={{
            position: 'absolute',
            top: '50%',
            left: 0,
            whiteSpace: 'nowrap',
            fontSize: 10,
            fontWeight: 300,
            color: 'rgba(255,255,255,0.4)',
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

export default function AdBar() {
  return (
    <div
      className="fixed left-60 right-0 z-30 flex h-[48px] items-center justify-center gap-4"
      style={{
        top: 84,
        background: 'rgba(18,30,48,0.97)',
        backdropFilter: 'blur(12px)',
      }}
    >
      <AdSlot
        ads={BONUP_ADS}
        dotColor="#F5A623"
        accentBorder="#F5A623"
        borderColor="rgba(245,166,35,0.2)"
        startDelayMs={0}
      />
      <AdSlot
        ads={PARTNER_ADS}
        dotColor="#8B5CF6"
        accentBorder="#8B5CF6"
        borderColor="rgba(139,92,246,0.2)"
        startDelayMs={6000}
      />
    </div>
  )
}
