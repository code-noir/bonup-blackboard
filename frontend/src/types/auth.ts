export type SubscriptionTier =
  | 'trial'
  | 'sol_member'
  | 'per_contract'
  | 'basic'
  | 'professional'
  | 'advanced'
  | 'starter'
  | 'business'
  | 'anchor'

export interface TokenPair {
  access: string
  refresh: string
}

export interface AuthUser {
  id: number
  username?: string
  email: string
  first_name: string
  last_name: string
  bon_id?: string
  subscription_tier?: SubscriptionTier
  effective_blackbod_tier?: 'basic' | 'professional' | 'advanced' | null
  has_blackbod_access?: boolean
  trial_start?: string | null
  trial_end?: string | null
  trial_valid?: boolean
  trial_ends_at?: string | null
  trial_expired?: boolean
  is_staff?: boolean
}

export interface AuthState {
  user: AuthUser | null
  accessToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
}

export interface OperatorUser {
  id: number
  email: string
  first_name: string
  last_name: string
  is_active: boolean
  is_super_admin: boolean
  is_super_operator: boolean
  is_legacy_placeholder: boolean
  user_id?: number | null
  bon_id?: string | null
  permissions: string[]
  can_view_as_user: boolean
  last_login_at?: string | null
  created_at?: string
}
