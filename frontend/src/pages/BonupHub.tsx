import { useEffect, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRightIcon,
  ChevronRightIcon,
  FolderOpenIcon,
  PlayIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline'
import api from '@/api/client'
import { nisloApi } from '@/api/nislo'
import type { FriendshipResponse, MyCommunity, NisloPerson } from '@/types/nislo'
import { useAuth } from '@/context/AuthContext'
import type { AuthUser } from '@/types/auth'
import { CanonicalAvatar } from '@/components/identity/CanonicalAvatar'
import '@/home.css'

type LoadState = 'loading' | 'success' | 'error'

type StorageSummary = {
  capacity_bytes: number
  used_bytes: number
  available_bytes: number
}

function displayName(user: AuthUser | null) {
  return [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'bonUP member'
}

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function formatBytes(value: number) {
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`
  return `${(value / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function personName(person: NisloPerson) {
  return person.display_name || [person.first_name, person.last_name].filter(Boolean).join(' ') || 'bonUP member'
}

function HomeSectionHeading({ title, description, to }: { title: string; description?: string; to?: string }) {
  return (
    <div className="home-section-heading">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {to && <Link className="home-card-link" to={to}>View all <ChevronRightIcon className="inline h-3 w-3" /></Link>}
    </div>
  )
}

function ProfileAvatar({ user }: { user: AuthUser | null }) {
  return <CanonicalAvatar identity={user || {}} className="home-profile-avatar" label="Profile avatar" />
}

function FeaturedMedia({ source, poster, title, description }: { source?: string; poster?: string; title: string; description: string }) {
  if (source) {
    return <video className="home-media-card" controls poster={poster} preload="metadata"><source src={source} /></video>
  }
  return (
    <div className="home-card home-media-card" aria-label="Featured bonUP media placeholder">
      <div className="home-media-poster">
        <span className="home-media-placeholder-label">bonUP feature</span>
        <button type="button" className="home-media-play home-media-play-disabled" disabled aria-label="Featured media is not available yet">
          <PlayIcon className="h-5 w-5" />
        </button>
        <div className="home-media-copy">
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </div>
    </div>
  )
}

function EmptyState({ title, children, to, label }: { title: string; children: ReactNode; to?: string; label?: string }) {
  return (
    <div className="home-empty">
      <strong>{title}</strong>
      <span>{children}</span>
      {to && <div><Link className="home-card-link" to={to}>{label || 'Explore bonUP'} <ArrowRightIcon className="inline h-3 w-3" /></Link></div>}
    </div>
  )
}

function PersonAvatar({ person, index }: { person: NisloPerson; index: number }) {
  return <CanonicalAvatar identity={person} className={`home-person-avatar home-person-avatar-${index % 4}`} label={`${personName(person)} avatar`} />
}

export default function BonupHub() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [storage, setStorage] = useState<StorageSummary | null>(null)
  const [communities, setCommunities] = useState<MyCommunity[]>([])
  const [friendships, setFriendships] = useState<FriendshipResponse | null>(null)
  const [states, setStates] = useState({
    storage: 'loading' as LoadState,
    communities: 'loading' as LoadState,
    friendships: 'loading' as LoadState,
  })

  useEffect(() => {
    let cancelled = false
    Promise.allSettled([
      api.get<StorageSummary>('/uploads/storage/'),
      nisloApi.communities(),
      nisloApi.friends(),
    ]).then(([storageResult, communitiesResult, friendshipsResult]) => {
      if (cancelled) return
      setStates({
        storage: storageResult.status === 'fulfilled' ? 'success' : 'error',
        communities: communitiesResult.status === 'fulfilled' ? 'success' : 'error',
        friendships: friendshipsResult.status === 'fulfilled' ? 'success' : 'error',
      })
      if (storageResult.status === 'fulfilled') setStorage(storageResult.value.data)
      if (communitiesResult.status === 'fulfilled') setCommunities(communitiesResult.value.results || [])
      if (friendshipsResult.status === 'fulfilled') setFriendships(friendshipsResult.value)
    })
    return () => { cancelled = true }
  }, [])

  const name = displayName(user)
  const acceptedFriends = friendships?.friends || []
  const incomingRequests = friendships?.incoming_requests || []
  const outgoingRequests = friendships?.outgoing_requests || []
  const requestCount = incomingRequests.length + outgoingRequests.length
  const storagePercent = storage ? Math.min(100, Math.round((storage.used_bytes / Math.max(storage.capacity_bytes, 1)) * 100)) : 0

  return (
    <div className="home-page">
      <section className="home-identity" aria-labelledby="home-greeting">
        <div className="home-identity-main">
          <ProfileAvatar user={user} />
          <div>
            <p className="home-eyebrow">Your bonUP home</p>
            <h1 id="home-greeting">{greeting()}, {name}.</h1>
            <div className="home-identity-meta">
              {user?.username && <span>@{user.username}</span>}
              {user?.bon_id && <span>Bon ID {user.bon_id}</span>}
              <span>Signed-in platform identity</span>
            </div>
          </div>
        </div>
        <div className="home-identity-actions">
          <Link className="home-button home-button-primary" to="/account">View Profile</Link>
          <Link className="home-button" to="/account">Edit Profile</Link>
        </div>
      </section>

      <section className="home-top-grid" aria-label="Featured bonUP content and personal summary">
        <FeaturedMedia title="A clearer way to move through your digital world." description="bonUP brings your identity, Communities, relationships, and personal activity into one place." />
        <article className="home-card home-summary-card">
          <div className="home-card-header"><div><h2>Your bonUP snapshot</h2><p>The people and places in your world.</p></div><UserGroupIcon className="h-5 w-5 text-slate-400" /></div>
          <div className="home-metric-grid">
            <div className="home-metric"><strong>{states.communities === 'success' ? communities.length : '—'}</strong><span>Your Communities</span></div>
            <div className="home-metric"><strong>{states.friendships === 'success' ? acceptedFriends.length : '—'}</strong><span>Your People</span></div>
            <div className="home-metric"><strong>{states.friendships === 'success' ? requestCount : '—'}</strong><span>Friend requests</span></div>
          </div>
        </article>
      </section>

      <section className="home-section">
        <HomeSectionHeading title="Your Communities" description="Communities where you have an active membership." to="/apps/nislo/communities" />
        {states.communities === 'error' ? <div className="home-unavailable">Community information is unavailable right now. Open Nislo to try again.</div> : communities.length === 0 ? <EmptyState title="Your Communities will appear here." to="/apps/nislo/discover" label="Discover Communities">Find people and request to join a Community.</EmptyState> : (
          <div className="home-shelf">
            {communities.map((community, index) => <button type="button" className="home-card home-community-card" key={community.id} onClick={() => navigate(`/apps/nislo/communities/${community.id}`)}><div className={`home-community-cover home-community-cover-${(index % 3) + 1}`}><span className="home-community-glyph">✦</span><span className="home-community-cover-label">Community</span></div><div className="home-community-body"><h3>{community.name}</h3><p>{community.description || 'Your active Community membership'}</p><div className="home-community-footer"><span className="home-community-owner">Active membership</span><ChevronRightIcon className="h-4 w-4 text-slate-400" /></div></div></button>)}
          </div>
        )}
      </section>

      <section className="home-section">
        <HomeSectionHeading title="Your People" description="Accepted Nislo friendships and relationship requests." to="/apps/nislo/friends" />
        {states.friendships === 'error' ? <div className="home-unavailable">People information is unavailable right now. Open Nislo to try again.</div> : acceptedFriends.length === 0 && requestCount === 0 ? <EmptyState title="Your circle is just getting started." to="/apps/nislo/discover" label="Discover People">Real bonUP identities and accepted friendships will appear here.</EmptyState> : (
          <>
            {acceptedFriends.length > 0 && <div className="home-shelf">{acceptedFriends.slice(0, 8).map((friend, index) => <div className="home-card home-person-card" key={friend.id || friend.user_id}><PersonAvatar person={friend} index={index} /><div className="home-person-card-copy"><strong>{personName(friend)}</strong><span>{friend.bon_id ? `Bon ID ${friend.bon_id}` : 'Accepted friend'}</span></div></div>)}</div>}
            {(incomingRequests.length > 0 || outgoingRequests.length > 0) && <div className="home-request-strip"><span>Friend requests</span><strong>{requestCount}</strong><Link className="home-card-link" to="/apps/nislo/friends">Review in Nislo <ArrowRightIcon className="inline h-3 w-3" /></Link></div>}
          </>
        )}
      </section>

      <section className="home-section home-lower-grid">
        <article className="home-card home-list-card">
          <HomeSectionHeading title="Social activity" description="Relationship activity from your bonUP world." to="/apps/nislo/friends" />
          {states.friendships === 'error' ? <div className="home-unavailable">Social activity is unavailable right now.</div> : incomingRequests.length === 0 ? <EmptyState title="No new social activity yet.">Friend requests and relationship updates will appear here.</EmptyState> : <div className="home-list">{incomingRequests.slice(0, 5).map((person) => <div className="home-list-row home-activity-row" key={person.id || person.user_id}><span className="home-activity-dot" /><div className="home-list-row-copy"><strong>{personName(person)}</strong><span>Sent you a friend request.</span></div><span className="home-activity-time">New</span></div>)}</div>}
        </article>
        <article className="home-card home-vault-card"><div className="home-card-header"><div><h2>Vault</h2><p>Your platform storage.</p></div><FolderOpenIcon className="h-5 w-5 text-slate-400" /></div>{states.storage === 'error' ? <div className="home-unavailable">Storage details unavailable. <Link className="home-card-link" to="/vault">Open Vault</Link></div> : storage ? <><div className="home-vault-meter" aria-label={`${storagePercent}% of Vault storage used`}><span style={{ width: `${storagePercent}%` }} /></div><div className="home-vault-stats"><span>{formatBytes(storage.used_bytes)} used</span><span>{formatBytes(storage.available_bytes)} available</span></div><Link className="home-button home-button-primary mt-5 inline-block" to="/vault">Open Vault</Link></> : <div className="home-unavailable">Loading storage details…</div>}</article>
      </section>

      <section className="home-section" aria-labelledby="blackboard-entry-title">
        <article className="home-card home-blackboard-card">
          <div>
            <p className="home-eyebrow">Blackboard</p>
            <h2 id="blackboard-entry-title">Structured agreements for commitments that matter.</h2>
          </div>
          <div className="home-blackboard-actions">
            {user?.has_blackbod_access === true ? <><Link className="home-button home-button-primary" state={{ blackbodEntry: true }} to="/apps/blackbod/contracts/new">+ New Agreement</Link><Link className="home-button" state={{ blackbodEntry: true }} to="/apps/blackbod">Open Blackboard</Link></> : <Link className="home-button" to="/store">Learn about Blackboard</Link>}
          </div>
        </article>
      </section>
    </div>
  )
}
