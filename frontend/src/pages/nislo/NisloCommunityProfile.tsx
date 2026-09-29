import { useEffect, useState } from 'react'
import { ArrowLeftIcon, LockClosedIcon } from '@heroicons/react/24/outline'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { nisloApi } from '@/api/nislo'
import type { CommunityProfile } from '@/types/nislo'
import { NisloError, PersonAvatar, StatusPill } from '@/components/nislo/NisloPrimitives'

function errorMessage(error: unknown) {
  const response = (error as { response?: { data?: { detail?: string } } }).response
  return response?.data?.detail || 'This Community profile is unavailable.'
}

export default function NisloCommunityProfile() {
  const { communityId } = useParams<{ communityId: string }>()
  const navigate = useNavigate()
  const [community, setCommunity] = useState<CommunityProfile | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!communityId) return
    nisloApi.communityProfile(communityId).then(setCommunity).catch((requestError) => setError(errorMessage(requestError)))
  }, [communityId])

  const requestJoin = async () => {
    if (!communityId) return
    setBusy(true)
    setError('')
    try {
      await nisloApi.requestToJoin(communityId)
      setCommunity((current) => current ? { ...current, join_request_status: 'pending' } : current)
      setNotice('Your request is with the Community owner or admin.')
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  if (error) return <div className="nislo-page"><NisloError message={error} /><button type="button" className="nislo-button nislo-button-secondary" onClick={() => navigate('/apps/nislo/discover')}>Back to Discover</button></div>
  if (!community) return <div className="nislo-loading">Loading Community profile...</div>

  return (
    <div className="nislo-page">
      <button type="button" className="nislo-back-link" onClick={() => navigate(-1)}><ArrowLeftIcon className="h-4 w-4" /> Back to Discover</button>
      <section className="nislo-profile-hero">
        <div className="nislo-profile-meta"><StatusPill tone="gold"><LockClosedIcon className="mr-1 inline h-3 w-3" /> Private</StatusPill><StatusPill>{community.member_count} members</StatusPill>{community.membership_status === 'member' && <StatusPill tone="teal">Your Community</StatusPill>}</div>
        <h1>{community.name}</h1>
        <p>{community.description || 'A private place for people with something in common.'}</p>
      </section>
      {notice && <div className="nislo-inline-success" role="status">{notice}</div>}
      <div className="nislo-profile-body">
        <section className="nislo-panel">
          <div className="nislo-section-heading"><div><p className="nislo-section-eyebrow">Inside the circle</p><h2>Member preview</h2></div></div>
          <div className="nislo-profile-members">{community.members_preview.map((member) => <div className="nislo-member-chip" key={member.user_id}><PersonAvatar person={member} />{member.display_name}</div>)}</div>
          <p className="nislo-panel-copy">This preview is public discovery metadata only. Private conversations, files, Topics, events, and gatherings remain available only to active members.</p>
        </section>
        <aside className="nislo-panel">
          <p className="nislo-section-eyebrow">Your relationship</p>
          <h2 className="nislo-aside-title">{community.membership_status === 'member' ? 'You are in.' : community.membership_status === 'removed' ? 'Membership removed' : 'Not a member yet'}</h2>
          {community.membership_status === 'member' && <StatusPill tone="teal">{community.membership_role || 'member'}</StatusPill>}
          {community.join_request_status === 'pending' && <StatusPill tone="gold">Request pending</StatusPill>}
          {community.can_request_join && !community.join_request_status && community.membership_status !== 'member' && <button type="button" className="nislo-button nislo-button-primary nislo-full-button" onClick={() => void requestJoin()} disabled={busy}>{busy ? 'Sending request...' : 'Request to Join'}</button>}
          {community.membership_status === 'member' && <Link to={`/apps/nislo/communities/${community.id}/workspace`} className="nislo-button nislo-button-primary nislo-full-button">Open Community</Link>}
        </aside>
      </div>
    </div>
  )
}
