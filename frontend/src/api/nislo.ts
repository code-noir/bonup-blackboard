import api from '@/api/client'
import type {
  CommunityProfile,
  CommunityWorkspace,
  FriendshipResponse,
  JoinRequest,
  JoinRequestResponse,
  MyCommunity,
  NisloPerson,
} from '@/types/nislo'

// Nislo screens must always be able to leave their loading state, even when
// the API server or database stops responding.
export const NISLO_REQUEST_TIMEOUT_MS = 10000

async function nisloGet<T>(path: string) {
  const { data } = await api.get<T>(path, { timeout: NISLO_REQUEST_TIMEOUT_MS })
  return data
}

async function nisloPost<T>(path: string, payload: unknown) {
  const { data } = await api.post<T>(path, payload, { timeout: NISLO_REQUEST_TIMEOUT_MS })
  return data
}

async function nisloPatch<T>(path: string, payload: unknown) {
  const { data } = await api.patch<T>(path, payload, { timeout: NISLO_REQUEST_TIMEOUT_MS })
  return data
}

export const nisloApi = {
  async discover(query = '') {
    return nisloGet<{ count: number; results: CommunityProfile[] }>(
      `/communities/discover/${query ? `?q=${encodeURIComponent(query)}` : ''}`,
    )
  },

  async communityProfile(id: string) {
    return nisloGet<CommunityProfile>(`/communities/discover/${id}/`)
  },

  async communityWorkspace(id: string) {
    return nisloGet<CommunityWorkspace>(`/communities/${id}/members/`)
  },

  async updateCommunity(id: string, name: string, description: string) {
    return nisloPatch<MyCommunity>(`/communities/${id}/`, { name, description })
  },

  async people(query: string) {
    return nisloGet<{ count: number; results: NisloPerson[] }>(
      `/communities/people/?q=${encodeURIComponent(query)}`,
    )
  },

  async friends() {
    return nisloGet<FriendshipResponse>('/communities/friends/')
  },

  async sendFriendRequest(bonId: string) {
    return nisloPost<NisloPerson>('/communities/friends/', { bon_id: bonId })
  },

  async respondToFriendRequest(id: string, decision: 'accept' | 'decline') {
    return nisloPost<NisloPerson>(`/communities/friends/requests/${id}/${decision}/`, {})
  },

  async communities() {
    return nisloGet<{ count: number; results: MyCommunity[] }>('/communities/')
  },

  async createCommunity(name: string, description: string) {
    return nisloPost<MyCommunity>('/communities/', { name, description })
  },

  async requestToJoin(communityId: string) {
    return nisloPost<JoinRequest>(`/communities/${communityId}/join-requests/`, {})
  },

  async joinRequests() {
    return nisloGet<JoinRequestResponse>('/communities/join-requests/')
  },

  async reviewJoinRequest(id: string, decision: 'approve' | 'decline') {
    return nisloPost<JoinRequest>(`/communities/join-requests/${id}/${decision}/`, {})
  },

  async invitations() {
    return nisloGet<Array<{ id: string; invitee_email: string; invitee_name: string; status: string; expires_at: string }>>('/users/me/invitations/')
  },

  async invitePerson(inviteeEmail: string, inviteeName: string) {
    return nisloPost('/users/me/invitations/', {
      invitee_email: inviteeEmail,
      invitee_name: inviteeName,
    })
  },
}
