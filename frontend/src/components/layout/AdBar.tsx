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
      className="flex flex-1 items-center justify-center px-6"
      style={{ backgroundColor: bg }}
    >
      <p
        className="text-[12px] font-medium tracking-wide transition-opacity duration-300"
        style={{ color, opacity: visible ? 1 : 0 }}
      >
        {ads[index]}
      </p>
    </div>
  )
}

export default function AdBar() {
  return (
    <div className="fixed top-[104px] left-60 right-0 z-30 flex h-[52px]">
      <AdSlot ads={BONUP_ADS}    bg="#0F1F3D" color="#ffffff" offsetMs={0}    />
      <AdSlot ads={PARTNER_ADS} bg="#F5A623" color="#0F1F3D" offsetMs={2000} />
    </div>
  )
}
