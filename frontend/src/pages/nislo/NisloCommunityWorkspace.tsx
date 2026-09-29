import {
  ArrowLeftIcon,
  ChatBubbleLeftRightIcon,
  DocumentTextIcon,
  HomeIcon,
  LockClosedIcon,
  PhotoIcon,
  UserGroupIcon,
  VideoCameraIcon,
} from '@heroicons/react/24/outline'
import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { nisloApi } from '@/api/nislo'
import { useAuth } from '@/context/AuthContext'
import type { CommunityMember, CommunityWorkspace, NisloPerson } from '@/types/nislo'
import { NisloError, PersonAvatar, StatusPill } from '@/components/nislo/NisloPrimitives'

function errorMessage(error: unknown) {
  const data = (error as { response?: { data?: { detail?: string; name?: string[] } } }).response?.data
  if (data?.detail) return data.detail
  if (data?.name?.[0]) return data.name[0]
  return 'This Community workspace is unavailable.'
}

function roleLabel(role: CommunityWorkspace['current_member_role']) {
  return role.charAt(0).toUpperCase() + role.slice(1)
}

function communityInitials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join('')
    .toUpperCase() || 'C'
}

function memberSummary(members: CommunityMember[], count: number) {
  const names = members.slice(0, 2).map((member) => member.display_name)
  if (!names.length) return `${count} ${count === 1 ? 'member' : 'members'}`
  if (count > names.length) return `${names.join(' and ')} and ${count - names.length} other${count - names.length === 1 ? '' : 's'}`
  return names.join(' and ')
}

function currentPerson(user: ReturnType<typeof useAuth>['user']): NisloPerson {
  return {
    user_id: user?.id || 0,
    bon_id: user?.bon_id || null,
    first_name: user?.first_name || '',
    last_name: user?.last_name || '',
    display_name: [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'You',
    profile_photo_url: user?.profile_photo_url || null,
  }
}

function MemberCard({ member }: { member: CommunityMember }) {
  const isLeader = member.role === 'owner' || member.role === 'admin'
  return (
    <article className="nislo-community-member-card">
      <PersonAvatar person={member} />
      <div className="nislo-community-member-card-copy">
        <strong>{member.display_name}</strong>
        <span>{member.bon_id ? `bonID ${member.bon_id}` : 'bonID not available'}</span>
      </div>
      <StatusPill tone={isLeader ? 'gold' : 'neutral'}>{roleLabel(member.role)}</StatusPill>
    </article>
  )
}

function FutureAction({ label, Icon }: { label: string; Icon: React.ElementType }) {
  return (
    <button type="button" className="nislo-community-future-action" disabled aria-disabled="true">
      <Icon className="h-4 w-4" />
      <span>{label}</span>
    </button>
  )
}

export default function NisloCommunityWorkspace() {
  const { communityId } = useParams<{ communityId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const [community, setCommunity] = useState<CommunityWorkspace | null>(null)
  const [error, setError] = useState('')
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editError, setEditError] = useState('')
  const [editNotice, setEditNotice] = useState('')
  const [savingDetails, setSavingDetails] = useState(false)

  useEffect(() => {
    if (!communityId) return
    setCommunity(null)
    setError('')
    nisloApi.communityWorkspace(communityId).then((loadedCommunity) => {
      setCommunity(loadedCommunity)
      setEditName(loadedCommunity.name)
      setEditDescription(loadedCommunity.description)
    }).catch((requestError) => setError(errorMessage(requestError)))
  }, [communityId])

  if (error) return <div className="nislo-page"><NisloError message={error} /><button type="button" className="nislo-button nislo-button-secondary" onClick={() => navigate('/apps/nislo/communities')}>Back to My Communities</button></div>
  if (!community) return <div className="nislo-loading">Entering Community...</div>

  const showingMembers = searchParams.get('view') === 'members'
  const showingSettings = searchParams.get('view') === 'settings'
  const isOwner = community.current_member_role === 'owner'
  const canManage = community.current_member_role === 'owner' || community.current_member_role === 'admin'
  const leaders = community.members.filter((member) => member.role === 'owner' || member.role === 'admin')
  const members = community.members.filter((member) => member.role !== 'owner' && member.role !== 'admin')
  const viewer = currentPerson(user)

  const saveDetails = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const name = editName.trim()
    if (!name) {
      setEditError('Community name is required.')
      return
    }
    if (name.length > 200) {
      setEditError('Community name must be 200 characters or fewer.')
      return
    }

    setSavingDetails(true)
    setEditError('')
    setEditNotice('')
    try {
      const updated = await nisloApi.updateCommunity(community.id, name, editDescription)
      setCommunity((current) => current ? { ...current, name: updated.name, description: updated.description } : current)
      setEditName(updated.name)
      setEditDescription(updated.description)
      setEditNotice('Community details saved.')
    } catch (requestError) {
      setEditError(errorMessage(requestError))
    } finally {
      setSavingDetails(false)
    }
  }

  return (
    <div className="nislo-community-workspace">
      <section className="nislo-community-cover" aria-label="Community cover placeholder">
        <span className="nislo-community-cover-label">Community space</span>
        <span className="nislo-community-cover-detail">A place for people to gather</span>
      </section>

      <section className="nislo-community-identity-card" aria-labelledby="community-name">
        <button type="button" className="nislo-community-back" onClick={() => navigate('/apps/nislo/communities')}>
          <ArrowLeftIcon className="h-4 w-4" /> Back to Nislo
        </button>
        <div className="nislo-community-identity-row">
          <div className="nislo-community-avatar" aria-hidden="true">{communityInitials(community.name)}</div>
          <div className="nislo-community-identity-copy">
            <div className="nislo-community-eyebrow"><LockClosedIcon className="h-3.5 w-3.5" /> Private Community</div>
            <h1 id="community-name">{community.name}</h1>
            <p>{community.description || 'A private place for people with something in common.'}</p>
            <div className="nislo-community-quiet-meta">
              <span>{community.member_count} {community.member_count === 1 ? 'member' : 'members'}</span>
              <span>Your role: {roleLabel(community.current_member_role)}</span>
            </div>
            <div className="nislo-community-member-summary">
              <div className="nislo-community-member-stack" aria-label={`${community.member_count} Community members`}>
                {community.members.slice(0, 5).map((member) => <PersonAvatar key={member.user_id} person={member} />)}
                {community.member_count > 5 && <span className="nislo-member-more">+{community.member_count - 5}</span>}
              </div>
              <span>{memberSummary(community.members, community.member_count)}</span>
            </div>
          </div>
          <div className="nislo-community-identity-actions">
            <Link className="nislo-button nislo-button-primary" to="/apps/nislo/invites?invite=1">Invite</Link>
            {isOwner && <Link className="nislo-button nislo-button-secondary" to={`/apps/nislo/communities/${community.id}/workspace?view=settings`}>Edit</Link>}
          </div>
        </div>
      </section>

      <div className="nislo-community-layout">
        <aside className="nislo-community-nav" aria-label="Community navigation">
          <p className="nislo-community-nav-label">Community</p>
          <Link className={!showingMembers && !showingSettings ? 'nislo-community-nav-item nislo-community-nav-item-active' : 'nislo-community-nav-item'} to={`/apps/nislo/communities/${community.id}/workspace`}><HomeIcon className="h-4 w-4" /> Home</Link>
          <Link className={showingMembers ? 'nislo-community-nav-item nislo-community-nav-item-active' : 'nislo-community-nav-item'} to={`/apps/nislo/communities/${community.id}/workspace?view=members`}><UserGroupIcon className="h-4 w-4" /> Members</Link>
          <button type="button" className="nislo-community-nav-item nislo-community-nav-disabled" disabled aria-disabled="true">Topics <span>Coming soon</span></button>
          <button type="button" className="nislo-community-nav-item nislo-community-nav-disabled" disabled aria-disabled="true">Events <span>Coming soon</span></button>
          <button type="button" className="nislo-community-nav-item nislo-community-nav-disabled" disabled aria-disabled="true">Gatherings <span>Coming soon</span></button>
          <button type="button" className="nislo-community-nav-item nislo-community-nav-disabled" disabled aria-disabled="true">Media <span>Coming soon</span></button>
          <Link className={showingSettings ? 'nislo-community-nav-item nislo-community-nav-item-active' : 'nislo-community-nav-item'} to={`/apps/nislo/communities/${community.id}/workspace?view=settings`}>Settings</Link>
          {canManage && <Link className="nislo-community-manage-link" to="/apps/nislo/invites">Manage join requests</Link>}
        </aside>

        <main className="nislo-community-content" aria-live="polite">
          {showingSettings ? (
            <section className="nislo-community-panel" aria-labelledby="community-details-title">
              <div className="nislo-community-section-heading">
                <div><p className="nislo-section-eyebrow">Community settings</p><h2 id="community-details-title">Community Details</h2></div>
              </div>
              {!isOwner && <p className="nislo-panel-copy">Only the Community owner can edit its identity. You can view the current details here.</p>}
              {editError && <div className="nislo-inline-error" role="alert">{editError}</div>}
              {editNotice && <div className="nislo-inline-success" role="status">{editNotice}</div>}
              {isOwner ? (
                <form className="nislo-form" onSubmit={(event) => void saveDetails(event)}>
                  <label>Community name<input value={editName} maxLength={200} onChange={(event) => setEditName(event.target.value)} /></label>
                  <label>Description<textarea value={editDescription} onChange={(event) => setEditDescription(event.target.value)} /></label>
                  <div className="nislo-card-actions"><Link className="nislo-button nislo-button-secondary" to={`/apps/nislo/communities/${community.id}/workspace`}>Cancel</Link><button type="submit" className="nislo-button nislo-button-primary" disabled={savingDetails}>{savingDetails ? 'Saving...' : 'Save Changes'}</button></div>
                </form>
              ) : (
                <div className="nislo-form">
                  <label>Community name<input value={community.name} readOnly /></label>
                  <label>Description<textarea value={community.description} readOnly /></label>
                </div>
              )}
            </section>
          ) : showingMembers ? (
            <section className="nislo-community-panel nislo-community-members-panel">
              <div className="nislo-community-section-heading"><div><p className="nislo-section-eyebrow">People in this Community</p><h2>Members</h2></div><span className="nislo-community-section-count">{community.member_count} {community.member_count === 1 ? 'member' : 'members'}</span></div>
              {leaders.length > 0 && <div className="nislo-community-member-group"><h3>Community leaders</h3><div className="nislo-community-member-grid">{leaders.map((member) => <MemberCard key={member.user_id} member={member} />)}</div></div>}
              {members.length > 0 && <div className="nislo-community-member-group"><h3>Members</h3><div className="nislo-community-member-grid">{members.map((member) => <MemberCard key={member.user_id} member={member} />)}</div></div>}
              {!community.members.length && <div className="nislo-community-empty"><UserGroupIcon className="h-6 w-6" /><strong>No members to show yet.</strong><span>This Community is ready for its people.</span></div>}
            </section>
          ) : (
            <>
              <section className="nislo-community-panel nislo-community-pinned">
                <div className="nislo-community-section-heading"><div><p className="nislo-section-eyebrow">Community Home · Important</p><h2>Pinned / important</h2></div><span className="nislo-community-section-note">Nothing pinned yet</span></div>
                <div className="nislo-community-empty nislo-community-empty-compact"><span className="nislo-community-empty-mark">✦</span><div><strong>Your shared notes will live here.</strong><span>No pinned Community information has been added yet.</span></div></div>
              </section>

              <section className="nislo-community-panel nislo-community-composer">
                <div className="nislo-community-composer-head"><PersonAvatar person={viewer} /><div><strong>Share something with the community...</strong><span>Posting will be available when Community conversation is enabled.</span></div></div>
                <div className="nislo-community-composer-actions" aria-label="Future Community post actions">
                  <FutureAction label="Photo" Icon={PhotoIcon} />
                  <FutureAction label="Video" Icon={VideoCameraIcon} />
                  <FutureAction label="Document" Icon={DocumentTextIcon} />
                </div>
              </section>

              <section className="nislo-community-panel nislo-community-activity">
                <div className="nislo-community-section-heading"><div><p className="nislo-section-eyebrow">Community life</p><h2>Activity</h2></div><ChatBubbleLeftRightIcon className="h-5 w-5 text-slate-400" /></div>
                <div className="nislo-community-empty"><ChatBubbleLeftRightIcon className="h-7 w-7" /><strong>This Community is ready for its first conversation.</strong><span>When people begin sharing, their Community history will appear here.</span></div>
              </section>

              <section className="nislo-community-panel nislo-community-people-preview">
                <div className="nislo-community-section-heading"><div><p className="nislo-section-eyebrow">People make the place</p><h2>Member preview</h2></div><Link className="nislo-text-action" to={`/apps/nislo/communities/${community.id}/workspace?view=members`}>View all</Link></div>
                <div className="nislo-community-preview-grid">{community.members.slice(0, 6).map((member) => <div className="nislo-community-preview-person" key={member.user_id}><PersonAvatar person={member} /><strong>{member.display_name}</strong><span>{roleLabel(member.role)}</span></div>)}</div>
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  )
}
