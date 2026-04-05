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
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const boot = setTimeout(() => {
      const id = setInterval(() => {
        setVisible(false)
        setTimeout(() => {
          setIndex((i) => (i + 1) % ads.length)
          setVisible(true)
        }, 350)
      }, 4000)
      return () => clearInterval(id)
    }, offsetMs)
    return () => clearTimeout(boot)
  }, [ads.length, offsetMs])

  return (
    <div
      className="flex h-9 w-[200px] items-center justify-center rounded-lg px-4"
      style={{ backgroundColor: bg }}
    >
      <p
        className="text-[11px] font-medium tracking-wide transition-opacity duration-300 text-center"
        style={{ color, opacity: visible ? 1 : 0 }}
      >
        {ads[index]}
      </p>
    </div>
  )
}

export default function AdBar() {
  return (
    // Same grid as the dashboard stat cards: grid-cols-4 gap-4 px-6
    // col-span-2 + justify-center centers each banner over the
    // gap between cols 1–2 and cols 3–4 respectively.
    <div className="fixed top-[104px] left-60 right-0 z-30 h-[52px] border-b border-slate-200 bg-[#F7F8FA]">
      <div className="grid h-full grid-cols-4 items-center gap-4 px-6">
        <div className="col-span-2 flex justify-center">
          <AdSlot ads={BONUP_ADS} bg="#0F1F3D" color="#ffffff" offsetMs={0} />
        </div>
        <div className="col-span-2 flex justify-center">
          <AdSlot ads={PARTNER_ADS} bg="#F5A623" color="#0F1F3D" offsetMs={2000} />
        </div>
      </div>
    </div>
  )
}
