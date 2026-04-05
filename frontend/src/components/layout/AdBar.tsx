import { useState, useEffect } from 'react'

const BONUP_ADS = [
  'bonUP Pro — Upgrade your experience',
  'bonUP Templates — Start any contract in seconds',
  'bonUP Sessions — Go live with your partner',
  'bonUP Sol — Manage your payments seamlessly',
]

const PARTNER_ADS = [
  'Advertise with bonUP — Reach your audience',
  'Partner Spotlight — Coming soon',
  'Your brand here — Contact us',
  'bonUP Partners — Growing network',
]

function AdSlot({
  ads,
  bg,
  color,
  offsetMs = 0,
}: {
  ads: string[]
  bg: string
  color: string
  offsetMs?: number
}) {
  const [index, setIndex] = useState(0)
  const [active, setActive] = useState(offsetMs === 0)

  // For the gold banner, wait for the offset before showing the first ad
  useEffect(() => {
    if (offsetMs === 0) return
    const t = setTimeout(() => setActive(true), offsetMs)
    return () => clearTimeout(t)
  }, [offsetMs])

  return (
    <div
      className="relative h-9 w-[200px] overflow-hidden rounded-lg"
      style={{ backgroundColor: bg }}
    >
      {active && (
        // key={index} unmounts+remounts the span each cycle, restarting the animation
        <span
          key={index}
          onAnimationEnd={() => setIndex((i) => (i + 1) % ads.length)}
          style={{
            position: 'absolute',
            top: '50%',
            left: 0,
            color,
            whiteSpace: 'nowrap',
            fontSize: '11px',
            fontWeight: 500,
            letterSpacing: '0.025em',
            animation: 'bonup-marquee 4s linear forwards',
          }}
        >
          {ads[index]}
        </span>
      )}
    </div>
  )
}

export default function AdBar() {
  return (
    <div className="fixed top-[104px] left-60 right-0 z-30 h-[52px] border-b border-slate-200 bg-[#F7F8FA]">
      <div className="grid h-full grid-cols-4 items-center gap-4 px-6">
        <div className="col-span-2 flex justify-center">
          <AdSlot ads={BONUP_ADS}   bg="#0F1F3D" color="#ffffff" offsetMs={0}    />
        </div>
        <div className="col-span-2 flex justify-center">
          <AdSlot ads={PARTNER_ADS} bg="#F5A623" color="#0F1F3D" offsetMs={6000} />
        </div>
      </div>
    </div>
  )
}
