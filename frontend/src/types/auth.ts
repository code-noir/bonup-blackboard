export type SubscriptionTier =
  | 'trial'
  | 'sol_member'
  | 'per_contract'
  | 'starter'
  | 'professional'
  | 'business'
  | 'anchor'

export interface TokenPair {
  access: string
  refresh: string
}

export interface AuthUser {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  bon_id?: string
  subscription_tier?: SubscriptionTier
  trial_ends_at?: string | null
  trial_expired?: boolean
}

export interface AuthState {
  user: AuthUser | null
  accessToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
}
