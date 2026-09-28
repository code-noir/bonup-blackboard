import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import './blackboard-entry.css'

const BLACKBOD_ENTRY_TIMELINE = {
  workspaceRevealMs: 6000,
  landingDurationMs: 2000,
  totalDurationMs: 8000,
} as const

type EntryPhase = 'entering' | 'arriving' | 'complete'

function EntrySurface({ exiting = false }: { exiting?: boolean }) {
  return (
    <main
      className={`blackboard-entry-screen${exiting ? ' blackboard-entry-screen-exiting' : ''}`}
      aria-live={exiting ? 'off' : 'polite'}
      role={exiting ? undefined : 'status'}
      aria-hidden={exiting}
      aria-label="Entering Blackbod"
    >
      <div className="blackboard-entry-panel">
        <p className="blackboard-entry-kicker">BLACKBOD</p>
        <p className="blackboard-entry-message">Preparing your workspace...</p>
        <div className="blackboard-entry-progress" aria-hidden="true">
          <span />
        </div>
      </div>
    </main>
  )
}

/**
 * A bounded application-entry handoff. This component is mounted once by the
 * Blackboard application route, so nested Blackboard navigation does not
 * replay the entry state.
 */
export default function BlackboardEntryTransition({ children }: { children: ReactNode }) {
  const location = useLocation()
  const isBoundaryEntry = location.state?.blackbodEntry === true
  const [phase, setPhase] = useState<EntryPhase>(() => isBoundaryEntry ? 'entering' : 'complete')

  useEffect(() => {
    if (!isBoundaryEntry) return undefined

    const arrivalTimer = window.setTimeout(
      () => setPhase('arriving'),
      BLACKBOD_ENTRY_TIMELINE.workspaceRevealMs,
    )
    const completeTimer = window.setTimeout(
      () => setPhase('complete'),
      BLACKBOD_ENTRY_TIMELINE.totalDurationMs,
    )
    return () => {
      window.clearTimeout(arrivalTimer)
      window.clearTimeout(completeTimer)
    }
  }, [isBoundaryEntry])

  if (!isBoundaryEntry || phase === 'complete') return children
  if (phase === 'entering') return <EntrySurface />

  return (
    <div
      className="blackboard-entry-destination"
      style={{
        '--blackbod-landing-duration': `${BLACKBOD_ENTRY_TIMELINE.landingDurationMs}ms`,
      } as CSSProperties}
    >
      {children}
      <EntrySurface exiting />
    </div>
  )
}
