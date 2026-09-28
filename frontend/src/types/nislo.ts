export type FriendshipStatus = 'pending' | 'accepted' | 'declined' | 'pending_outgoing' | 'pending_incoming' | 'none'

export interface NisloPerson {
  user_id: number
  bon_id: string | null
  first_name: string
  last_name: string
  display_name: string
  relationship_status?: FriendshipStatus
  id?: string
  status?: string
  requester_id?: number
  recipient_id?: number
}

export interface CommunityProfile {
  id: string
  name: string
  description: string
  is_private: boolean
  member_count: number
  members_preview: NisloPerson[]
  owner: NisloPerson
  membership_status: 'not_member' | 'removed' | 'member'
  membership_role: 'owner' | 'admin' | 'moderator' | 'member' | null
  join_request_status: 'pending' | 'approved' | 'declined' | null
  can_request_join: boolean
  can_manage_join_requests: boolean
  created_at: string
}

export interface MyCommunity {
  id: string
  owner: number
  name: string
  description: string
  is_private: boolean
  is_discoverable: boolean
  created_at: string
  updated_at: string
}

export interface JoinRequest {
  id: string
  community: string
  community_name: string
  user: number
  requester_name: string
  status: 'pending' | 'approved' | 'declined'
  reviewer_name: string | null
  created_at: string
  reviewed_at: string | null
}

export interface FriendshipResponse {
  friends: NisloPerson[]
  incoming_requests: NisloPerson[]
  outgoing_requests: NisloPerson[]
}

export interface JoinRequestResponse {
  incoming: JoinRequest[]
  outgoing: JoinRequest[]
}
