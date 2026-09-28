import { useEffect, useState } from 'react'
import { UserGroupIcon } from '@heroicons/react/24/outline'
import { nisloApi } from '@/api/nislo'
import type { FriendshipResponse, NisloPerson } from '@/types/nislo'
import { NisloError, PersonAvatar, SectionHeading, StatusPill } from '@/components/nislo/NisloPrimitives'

function errorMessage(error: unknown) {
  const response = (error as { response?: { data?: { detail?: string } } }).response
  return response?.data?.detail || 'Nislo could not complete that request. Please try again.'
}

function FriendRow({ person, action }: { person: NisloPerson; action?: React.ReactNode }) {
  return (
    <div className="nislo-list-row">
      <div className="nislo-list-row-main">
        <PersonAvatar person={person} />
        <div className="nislo-list-row-copy">
          <strong>{person.display_name}</strong>
          <span>bonID {person.bon_id}</span>
        </div>
      </div>
      {action && <div className="nislo-list-row-actions">{action}</div>}
    </div>
  )
}

export default function NisloFriends() {
  const [data, setData] = useState<FriendshipResponse | null>(null)
  const [error, setError] = useState('')

  const load = async () => {
    try {
      setData(await nisloApi.friends())
    } catch (requestError) {
      setError(errorMessage(requestError))
    }
  }

  useEffect(() => { void load() }, [])

  const respond = async (id: string, decision: 'accept' | 'decline') => {
    try {
      await nisloApi.respondToFriendRequest(id, decision)
      await load()
    } catch (requestError) {
      setError(errorMessage(requestError))
    }
  }

  if (!data && !error) return <div className="nislo-loading">Loading your circle...</div>

  return (
    <div className="nislo-page">
      <div className="nislo-page-hero">
        <div>
          <p className="nislo-kicker">Nislo / Friends</p>
          <h1>Your circle.</h1>
          <p>Friendships are mutual, intentional, and shared across bonUP. Your accepted connections can help open the door to a Community.</p>
        </div>
        <div className="nislo-hero-stat"><UserGroupIcon className="h-5 w-5" /><strong>{data?.friends.length || 0}</strong><span>accepted friends</span></div>
      </div>
      {error && <NisloError message={error} />}
      <div className="nislo-panel-grid">
        <section className="nislo-panel">
          <SectionHeading title="Accepted friends" />
          {data?.friends.length ? <div className="nislo-list">{data.friends.map((person) => <FriendRow key={person.id} person={person} action={<StatusPill tone="teal">Friends</StatusPill>} />)}</div> : <div className="nislo-empty"><strong>Your circle is just beginning.</strong>Search Discover to find someone you know.</div>}
        </section>
        <section className="nislo-panel">
          <SectionHeading title="Incoming requests" />
          {data?.incoming_requests.length ? <div className="nislo-list">{data.incoming_requests.map((person) => <FriendRow key={person.id} person={person} action={<><button type="button" className="nislo-button nislo-button-primary" onClick={() => void respond(person.id || '', 'accept')}>Accept</button><button type="button" className="nislo-button nislo-button-danger" onClick={() => void respond(person.id || '', 'decline')}>Decline</button></>} />)}</div> : <div className="nislo-empty"><strong>No pending requests.</strong>New friend requests will appear here.</div>}
        </section>
      </div>
      <section className="nislo-section">
        <SectionHeading title="Outgoing requests" />
        {data?.outgoing_requests.length ? <div className="nislo-list">{data.outgoing_requests.map((person) => <FriendRow key={person.id} person={person} action={<StatusPill tone="gold">Waiting for response</StatusPill>} />)}</div> : <div className="nislo-empty"><strong>No outgoing requests.</strong>Use Discover to connect with someone.</div>}
      </section>
    </div>
  )
}
