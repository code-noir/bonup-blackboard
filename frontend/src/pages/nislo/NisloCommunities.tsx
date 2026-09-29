import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { nisloApi } from '@/api/nislo'
import { useAuth } from '@/context/AuthContext'
import type { FriendshipResponse, MyCommunity } from '@/types/nislo'
import { NisloError, SectionHeading, StatusPill } from '@/components/nislo/NisloPrimitives'

function errorMessage(error: unknown) {
  const response = (error as { response?: { data?: { detail?: string } } }).response
  return response?.data?.detail || 'Nislo could not complete that request. Please try again.'
}

export default function NisloCommunities() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [communities, setCommunities] = useState<MyCommunity[]>([])
  const [friends, setFriends] = useState<FriendshipResponse | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [communitiesLoadError, setCommunitiesLoadError] = useState('')
  const [friendsLoadError, setFriendsLoadError] = useState('')
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState('')
  const [showCreate, setShowCreate] = useState(false)

  const load = async () => {
    setLoading(true)
    setError('')
    setCommunitiesLoadError('')
    setFriendsLoadError('')
    const [communityResult, friendResult] = await Promise.allSettled([nisloApi.communities(), nisloApi.friends()])

    if (communityResult.status === 'fulfilled') {
      setCommunities(communityResult.value.results)
    } else {
      setCommunitiesLoadError('Unable to load your Communities right now.')
    }
    if (friendResult.status === 'fulfilled') {
      setFriends(friendResult.value)
    } else {
      setFriendsLoadError('Unable to load your circle right now.')
    }
    setLoading(false)
  }

  useEffect(() => { void load() }, [])
  const canCreate = (friends?.friends.length || 0) > 0

  const create = async (event: FormEvent) => {
    event.preventDefault()
    if (!canCreate) return
    setError('')
    try {
      const community = await nisloApi.createCommunity(name, description)
      setCommunities((items) => [community, ...items])
      setName('')
      setDescription('')
      setShowCreate(false)
      setNotice('Your Community is ready. You are its owner.')
      navigate(`/apps/nislo/communities/${community.id}/workspace`)
    } catch (requestError) {
      setError(errorMessage(requestError))
    }
  }

  if (loading) return <div className="nislo-loading">Opening your Communities...</div>

  return (
    <div className="nislo-page">
      <div className="nislo-page-hero">
        <div>
          <p className="nislo-kicker">Nislo / My Communities</p>
          <h1>Your spaces.</h1>
          <p>Communities you actively belong to live here. Private content stays behind the membership boundary.</p>
        </div>
        <button type="button" className="nislo-button nislo-button-primary" onClick={() => setShowCreate((open) => !open)}>+ Create Community</button>
      </div>
      {error && <NisloError message={error} action={<button type="button" className="nislo-text-action" onClick={() => void load()}>Retry</button>} />}
      {notice && <div className="nislo-inline-success" role="status">{notice}</div>}
      {friendsLoadError ? <NisloError message={friendsLoadError} action={<button type="button" className="nislo-text-action" onClick={() => void load()}>Retry</button>} /> : !canCreate && <div className="nislo-gate-note"><strong>Build your circle first.</strong><span>You need at least one accepted friend before you can create a Community. Find someone you know in Discover.</span><Link to="/apps/nislo/discover" className="nislo-text-action">Find friends</Link></div>}
      {showCreate && (
        <section className="nislo-panel nislo-create-panel">
          <SectionHeading title="Create a private Community" />
          {!canCreate ? <div className="nislo-empty">Creation is unavailable until you have an accepted friend.</div> : <form className="nislo-form" onSubmit={create}>
            <label>Community name<input required value={name} onChange={(event) => setName(event.target.value)} placeholder="The people who..." /></label>
            <label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What brings your people together?" /></label>
            <div><button type="submit" className="nislo-button nislo-button-primary">Create private Community</button></div>
          </form>}
        </section>
      )}
      <section className="nislo-section">
        <SectionHeading eyebrow="Active membership" title={`${communities.length} Community${communities.length === 1 ? '' : 'ies'}`} />
        {communitiesLoadError ? <NisloError message={communitiesLoadError} action={<button type="button" className="nislo-text-action" onClick={() => void load()}>Retry</button>} /> : communities.length ? <div className="nislo-my-communities-grid">{communities.map((community, index) => <article className={`nislo-my-community-card nislo-my-community-${index % 4}`} key={community.id}>
          <div className="nislo-my-community-icon">✦</div>
          <div className="nislo-my-community-copy"><h3>{community.name}</h3><p>{community.description || 'A private Community on Nislo.'}</p><div><StatusPill tone="teal">Active member</StatusPill>{community.owner === user?.id && <StatusPill tone="gold">Owner</StatusPill>}</div></div>
          <button type="button" className="nislo-button nislo-button-primary" onClick={() => navigate(`/apps/nislo/communities/${community.id}/workspace`)}>Open Community</button>
        </article>)}</div> : <div className="nislo-empty"><strong>Your Nislo story starts here.</strong>You do not belong to a Community yet. Explore the Discover shelf or create one when your circle is ready.</div>}
      </section>
    </div>
  )
}
