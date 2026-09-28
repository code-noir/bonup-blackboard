import api from '@/api/client'
import type {
  CommunityProfile,
  FriendshipResponse,
  JoinRequest,
  JoinRequestResponse,
  MyCommunity,
  NisloPerson,
} from '@/types/nislo'

export const nisloApi = {
  async discover(query = '') {
    const { data } = await api.get<{ count: number; results: CommunityProfile[] }>(
      `/communities/discover/${query ? `?q=${encodeURIComponent(query)}` : ''}`,
    )
    return data
  },

  async communityProfile(id: string) {
    const { data } = await api.get<CommunityProfile>(`/communities/discover/${id}/`)
    return data
  },

  async people(query: string) {
    const { data } = await api.get<{ count: number; results: NisloPerson[] }>(
      `/communities/people/?q=${encodeURIComponent(query)}`,
    )
    return data
  },

  async friends() {
    const { data } = await api.get<FriendshipResponse>('/communities/friends/')
    return data
  },

  async sendFriendRequest(bonId: string) {
    const { data } = await api.post<NisloPerson>('/communities/friends/', { bon_id: bonId })
    return data
  },

  async respondToFriendRequest(id: string, decision: 'accept' | 'decline') {
    const { data } = await api.post<NisloPerson>(`/communities/friends/requests/${id}/${decision}/`, {})
    return data
  },

  async communities() {
    const { data } = await api.get<{ count: number; results: MyCommunity[] }>('/communities/')
    return data
  },

  async createCommunity(name: string, description: string) {
    const { data } = await api.post<MyCommunity>('/communities/', { name, description })
    return data
  },

  async requestToJoin(communityId: string) {
    const { data } = await api.post<JoinRequest>(`/communities/${communityId}/join-requests/`, {})
    return data
  },

  async joinRequests() {
    const { data } = await api.get<JoinRequestResponse>('/communities/join-requests/')
    return data
  },

  async reviewJoinRequest(id: string, decision: 'approve' | 'decline') {
    const { data } = await api.post<JoinRequest>(`/communities/join-requests/${id}/${decision}/`, {})
    return data
  },

  async invitations() {
    const { data } = await api.get('/users/me/invitations/')
    return data as Array<{ id: string; invitee_email: string; invitee_name: string; status: string; expires_at: string }>
  },

  async invitePerson(inviteeEmail: string, inviteeName: string) {
    const { data } = await api.post('/users/me/invitations/', {
      invitee_email: inviteeEmail,
      invitee_name: inviteeName,
    })
    return data
  },
}
