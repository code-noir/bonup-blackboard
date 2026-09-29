import { FormEvent, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { nisloApi } from '@/api/nislo'
import type { FriendshipResponse, JoinRequestResponse } from '@/types/nislo'
import { NisloError, SectionHeading, StatusPill } from '@/components/nislo/NisloPrimitives'

interface BonupInvitation {
  id: string
  invitee_email: string
  invitee_name: string
  status: string
  expires_at: string
}

function errorMessage(error: unknown) {
  const response = (error as { response?: { data?: { detail?: string; invitee_email?: string[] } } }).response
  return response?.data?.detail || response?.data?.invitee_email?.[0] || 'Nislo could not complete that request. Please try again.'
}

export default function NisloInvites() {
  const [searchParams] = useSearchParams()
  const [requests, setRequests] = useState<JoinRequestResponse | null>(null)
  const [friendRequests, setFriendRequests] = useState<FriendshipResponse | null>(null)
  const [invitations, setInvitations] = useState<BonupInvitation[]>([])
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [joinLoadError, setJoinLoadError] = useState('')
  const [invitationLoadError, setInvitationLoadError] = useState('')
  const [friendLoadError, setFriendLoadError] = useState('')
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    setJoinLoadError('')
    setInvitationLoadError('')
    setFriendLoadError('')
    const [joinResult, invitationResult, friendResult] = await Promise.allSettled([
      nisloApi.joinRequests(),
      nisloApi.invitations(),
      nisloApi.friends(),
    ])

    if (joinResult.status === 'fulfilled') {
      setRequests(joinResult.value)
    } else {
      setJoinLoadError('Unable to load Community requests right now.')
    }
    if (invitationResult.status === 'fulfilled') {
      setInvitations(invitationResult.value)
    } else {
      setInvitationLoadError('Unable to load invitations right now.')
    }
    if (friendResult.status === 'fulfilled') {
      setFriendRequests(friendResult.value)
    } else {
      setFriendLoadError('Unable to load friend requests right now.')
    }
    setLoading(false)
  }

  const respondToFriend = async (id: string, decision: 'accept' | 'decline') => {
    try {
      await nisloApi.respondToFriendRequest(id, decision)
      setNotice(decision === 'accept' ? 'Friend request accepted.' : 'Friend request declined.')
      await load()
    } catch (requestError) {
      setError(errorMessage(requestError))
    }
  }

  useEffect(() => { void load() }, [])

  const review = async (id: string, decision: 'approve' | 'decline') => {
    try {
      await nisloApi.reviewJoinRequest(id, decision)
      setNotice(decision === 'approve' ? 'Member approved.' : 'Request declined.')
      await load()
    } catch (requestError) {
      setError(errorMessage(requestError))
    }
  }

  const submitInvitation = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setNotice('')
    try {
      await nisloApi.invitePerson(email, name)
      setEmail('')
      setName('')
      setNotice('Invitation record created. Delivery and link sharing are not configured yet.')
      await load()
    } catch (requestError) {
      setError(errorMessage(requestError))
    }
  }

  if (loading) return <div className="nislo-loading">Opening your invitations...</div>

  return (
    <div className="nislo-page">
      <div className="nislo-page-hero">
        <div>
          <p className="nislo-kicker">Nislo / Invites</p>
          <h1>Open the door.</h1>
          <p>Manage friend requests, Community join requests, and invitations that help your circle find bonUP.</p>
        </div>
      </div>
      {error && <NisloError message={error} action={<button type="button" className="nislo-text-action" onClick={() => void load()}>Retry</button>} />}
      {notice && <div className="nislo-inline-success" role="status">{notice}</div>}
      <div className="nislo-panel-grid">
        <section className="nislo-panel">
          <SectionHeading title="Friend requests" />
          {friendLoadError ? <NisloError message={friendLoadError} action={<button type="button" className="nislo-text-action" onClick={() => void load()}>Retry</button>} /> : friendRequests?.incoming_requests.length ? <div className="nislo-list">{friendRequests.incoming_requests.map((request) => <div className="nislo-list-row" key={request.id}><div className="nislo-list-row-copy"><strong>{request.display_name}</strong><span>wants to connect with you</span></div><div className="nislo-list-row-actions"><button type="button" className="nislo-button nislo-button-primary" onClick={() => void respondToFriend(request.id || '', 'accept')}>Accept</button><button type="button" className="nislo-button nislo-button-danger" onClick={() => void respondToFriend(request.id || '', 'decline')}>Decline</button></div></div>)}</div> : <div className="nislo-empty"><strong>No friend requests.</strong>Friend requests will appear here.</div>}
          <div className="nislo-subsection"><p className="nislo-subsection-title">Outgoing</p>{friendLoadError ? <span className="nislo-muted-copy">Friend request data is unavailable.</span> : friendRequests?.outgoing_requests.length ? friendRequests.outgoing_requests.map((request) => <div className="nislo-request-line" key={request.id}><span>{request.display_name}</span><StatusPill tone="gold">Pending</StatusPill></div>) : <span className="nislo-muted-copy">No outgoing friend requests.</span>}</div>
        </section>
        <section className="nislo-panel">
          <SectionHeading title="Community requests" />
          {joinLoadError ? <NisloError message={joinLoadError} action={<button type="button" className="nislo-text-action" onClick={() => void load()}>Retry</button>} /> : requests?.incoming.length ? <div className="nislo-list">{requests.incoming.map((request) => <div className="nislo-list-row" key={request.id}><div className="nislo-list-row-copy"><strong>{request.requester_name}</strong><span> wants to join {request.community_name}</span></div><div className="nislo-list-row-actions"><button type="button" className="nislo-button nislo-button-primary" onClick={() => void review(request.id, 'approve')}>Approve</button><button type="button" className="nislo-button nislo-button-danger" onClick={() => void review(request.id, 'decline')}>Decline</button></div></div>)}</div> : <div className="nislo-empty"><strong>No requests to review.</strong>Owner and admin requests will appear here.</div>}
          <div className="nislo-subsection">
            <p className="nislo-subsection-title">Your outgoing requests</p>
            {joinLoadError ? <span className="nislo-muted-copy">Community request data is unavailable.</span> : requests?.outgoing.length ? requests.outgoing.map((request) => <div className="nislo-request-line" key={request.id}><span>{request.community_name}</span><StatusPill tone={request.status === 'pending' ? 'gold' : request.status === 'approved' ? 'teal' : 'neutral'}>{request.status}</StatusPill></div>) : <span className="nislo-muted-copy">You have not requested to join a Community.</span>}
          </div>
        </section>
        <section className="nislo-panel" id="invite-people">
          <SectionHeading title="Invite People" />
          <p className="nislo-panel-copy">Bring someone from WhatsApp, TikTok, or another circle toward bonUP with an invitation record. Email delivery and link sharing are not configured in this slice. Nislo never creates a friendship without their consent.</p>
          <form className="nislo-form" onSubmit={submitInvitation}>
            <label>Email<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="friend@example.com" /></label>
            <label>Name<input required value={name} onChange={(event) => setName(event.target.value)} placeholder="Their name" /></label>
            <button type="submit" className="nislo-button nislo-button-primary">Create invitation</button>
          </form>
          <div className="nislo-subsection">
            <p className="nislo-subsection-title">Recent invitations</p>
            {invitationLoadError ? <NisloError message={invitationLoadError} action={<button type="button" className="nislo-text-action" onClick={() => void load()}>Retry</button>} /> : invitations.length ? invitations.map((invitation) => <div className="nislo-request-line" key={invitation.id}><span>{invitation.invitee_name} <small>{invitation.invitee_email}</small></span><StatusPill>{invitation.status}</StatusPill></div>) : <span className="nislo-muted-copy">No invitations yet.</span>}
          </div>
        </section>
      </div>
      {searchParams.get('invite') === '1' && <p className="nislo-deep-link-note">You are in the right place to bring your people in.</p>}
    </div>
  )
}
