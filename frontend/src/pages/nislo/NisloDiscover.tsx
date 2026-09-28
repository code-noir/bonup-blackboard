import { FormEvent, useEffect, useState } from 'react'
import { ArrowRightIcon, MagnifyingGlassIcon, UserPlusIcon } from '@heroicons/react/24/outline'
import { useNavigate } from 'react-router-dom'
import { nisloApi } from '@/api/nislo'
import type { CommunityProfile, NisloPerson } from '@/types/nislo'
import { CommunityCard, NisloError, PersonAvatar, SectionHeading, StatusPill } from '@/components/nislo/NisloPrimitives'

function errorMessage(error: unknown) {
  const response = (error as { response?: { data?: { detail?: string } } }).response
  return response?.data?.detail || 'Nislo could not complete that request. Please try again.'
}

export default function NisloDiscover() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [communities, setCommunities] = useState<CommunityProfile[]>([])
  const [people, setPeople] = useState<NisloPerson[]>([])
  const [loading, setLoading] = useState(true)
  const [busyCommunity, setBusyCommunity] = useState<string | null>(null)
  const [error, setError] = useState('')

  const load = async (nextQuery = '') => {
    setLoading(true)
    setError('')
    try {
      const [communityData, peopleData] = await Promise.all([
        nisloApi.discover(nextQuery),
        nextQuery ? nisloApi.people(nextQuery) : Promise.resolve({ count: 0, results: [] as NisloPerson[] }),
      ])
      setCommunities(communityData.results)
      setPeople(peopleData.results)
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const submitSearch = (event: FormEvent) => {
    event.preventDefault()
    void load(query.trim())
  }

  const requestJoin = async (community: CommunityProfile) => {
    setBusyCommunity(community.id)
    setError('')
    try {
      await nisloApi.requestToJoin(community.id)
      setCommunities((items) => items.map((item) => item.id === community.id ? { ...item, join_request_status: 'pending' } : item))
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setBusyCommunity(null)
    }
  }

  const addFriend = async (person: NisloPerson) => {
    setError('')
    try {
      await nisloApi.sendFriendRequest(person.bon_id || '')
      setPeople((items) => items.map((item) => item.user_id === person.user_id ? { ...item, relationship_status: 'pending_outgoing' } : item))
    } catch (requestError) {
      setError(errorMessage(requestError))
    }
  }

  return (
    <div className="nislo-page">
      <div className="nislo-page-hero nislo-discover-hero">
        <div className="nislo-discover-hero-copy">
          <p className="nislo-kicker">Nislo / Discover</p>
          <h1>Find your people.</h1>
          <p>Explore private Communities, meet bonUP people, and bring your circle into a place that feels like yours.</p>
          <form className="nislo-search" onSubmit={submitSearch}>
            <MagnifyingGlassIcon className="h-5 w-5 shrink-0 text-[#7890ae]" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search Communities or people" aria-label="Search Communities or people" />
            <button type="submit">Search</button>
          </form>
        </div>
        <div className="nislo-hero-visual" aria-label="Development-only social image placeholder">
          <div className="nislo-hero-photo nislo-hero-photo-back"><span className="nislo-hero-silhouette nislo-hero-silhouette-teal" /></div>
          <div className="nislo-hero-photo nislo-hero-photo-front"><span className="nislo-hero-silhouette nislo-hero-silhouette-coral" /></div>
          <div className="nislo-hero-photo nislo-hero-photo-side"><span className="nislo-hero-silhouette nislo-hero-silhouette-purple" /></div>
          <div className="nislo-hero-visual-note"><span>✦</span><strong>Find your circle</strong><small>replaceable development imagery</small></div>
        </div>
      </div>

      {error && <NisloError message={error} />}
      {loading ? <div className="nislo-loading">Opening the nest...</div> : (
        <>
          <section className="nislo-section">
            <SectionHeading
              eyebrow="Explore together"
              title="Communities worth finding"
              action={<button type="button" className="nislo-text-action" onClick={() => void load(query.trim())}>Refresh <ArrowRightIcon className="h-4 w-4" /></button>}
            />
            {communities.length ? (
              <div className="nislo-shelf">
                {communities.map((community) => (
                  <CommunityCard
                    key={community.id}
                    community={community}
                    busy={busyCommunity === community.id}
                    onProfile={() => navigate(`/apps/nislo/communities/${community.id}`)}
                    onJoin={() => void requestJoin(community)}
                  />
                ))}
              </div>
            ) : <div className="nislo-empty"><strong>No Communities found yet.</strong>Try another search, or be the first to bring your people together.</div>}
          </section>

          <section className="nislo-section">
            <SectionHeading eyebrow="Real people, real circles" title="People you may know" />
            {people.length ? (
              <div className="nislo-people-grid">
                {people.map((person) => (
                  <div className="nislo-person-card" key={person.user_id}>
                    <PersonAvatar person={person} />
                    <div className="nislo-person-card-body">
                      <div className="nislo-person-card-name">{person.display_name}</div>
                      <div className="nislo-person-card-id">bonID {person.bon_id}</div>
                    </div>
                    {person.relationship_status === 'none' && <button type="button" className="nislo-button nislo-button-secondary" onClick={() => void addFriend(person)}><UserPlusIcon className="inline h-4 w-4" /> Add</button>}
                    {person.relationship_status === 'pending_outgoing' && <StatusPill tone="gold">Requested</StatusPill>}
                    {person.relationship_status === 'pending_incoming' && <StatusPill>Incoming request</StatusPill>}
                    {person.relationship_status === 'accepted' && <StatusPill tone="teal">Friends</StatusPill>}
                  </div>
                ))}
              </div>
            ) : <div className="nislo-empty"><strong>Search for someone you know.</strong>Use a name or bonID above. Nislo only shows the identity details needed to start a connection.</div>}
          </section>

          <section className="nislo-invite-panel">
            <div>
              <h3>Bring your people.</h3>
              <p>Already have a circle elsewhere? Invite them to bonUP by email and let friendship grow through a real, consent-based request.</p>
            </div>
            <button type="button" className="nislo-button nislo-button-primary" onClick={() => navigate('/apps/nislo/invites?invite=1')}>Invite People <ArrowRightIcon className="ml-1 inline h-4 w-4" /></button>
          </section>
        </>
      )}
    </div>
  )
}
