import type { ReactNode } from 'react'
import type { CommunityProfile, NisloPerson } from '@/types/nislo'

export function initials(person: NisloPerson) {
  return ([person.first_name?.[0], person.last_name?.[0]].filter(Boolean).join('') || person.display_name?.[0] || '?').toUpperCase()
}

export function PersonAvatar({ person, large = false }: { person: NisloPerson; large?: boolean }) {
  const colors = ['nislo-avatar-purple', 'nislo-avatar-blue', 'nislo-avatar-teal', 'nislo-avatar-coral']
  const color = colors[(person.user_id || 0) % colors.length]
  return <span className={`nislo-avatar ${large ? 'nislo-avatar-large' : ''} ${color}`}>{initials(person)}</span>
}

export function SectionHeading({ eyebrow, title, action }: { eyebrow?: string; title: string; action?: ReactNode }) {
  return (
    <div className="nislo-section-heading">
      <div>
        {eyebrow && <p className="nislo-section-eyebrow">{eyebrow}</p>}
        <h2>{title}</h2>
      </div>
      {action}
    </div>
  )
}

export function StatusPill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'gold' | 'teal' | 'danger' }) {
  return <span className={`nislo-status-pill nislo-status-${tone}`}>{children}</span>
}

export function CommunityCard({
  community,
  onProfile,
  onJoin,
  busy = false,
}: {
  community: CommunityProfile
  onProfile: () => void
  onJoin: () => void
  busy?: boolean
}) {
  const canJoin = community.can_request_join && !community.join_request_status && community.membership_status !== 'member'
  return (
    <article className="nislo-community-card">
      <div className={`nislo-cover nislo-cover-${community.id.slice(0, 2)}`}>
        <span className="nislo-cover-glyph">✦</span>
        <span className="nislo-cover-private">Private community</span>
      </div>
      <div className="nislo-community-card-body">
        <div className="nislo-card-title-row">
          <h3>{community.name}</h3>
          <StatusPill tone={community.membership_status === 'member' ? 'teal' : 'neutral'}>
            {community.membership_status === 'member' ? 'Member' : `${community.member_count} members`}
          </StatusPill>
        </div>
        <p className="nislo-card-description">{community.description || 'A private place for people with something in common.'}</p>
        <div className="nislo-member-stack" aria-label={`${community.member_count} members`}>
          {community.members_preview.slice(0, 4).map((member) => <PersonAvatar key={member.user_id} person={member} />)}
          {community.member_count > 4 && <span className="nislo-member-more">+{community.member_count - 4}</span>}
        </div>
        <div className="nislo-card-actions">
          <button type="button" className="nislo-button nislo-button-secondary" onClick={onProfile}>View Profile</button>
          {canJoin && <button type="button" className="nislo-button nislo-button-primary" onClick={onJoin} disabled={busy}>{busy ? 'Sending...' : 'Request to Join'}</button>}
          {community.join_request_status === 'pending' && <StatusPill tone="gold">Request pending</StatusPill>}
          {community.membership_status === 'member' && <StatusPill tone="teal">Your community</StatusPill>}
        </div>
      </div>
    </article>
  )
}

export function NisloError({ message }: { message: string }) {
  return <div className="nislo-inline-error" role="alert">{message}</div>
}
