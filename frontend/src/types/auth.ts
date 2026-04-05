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
}

export interface AuthState {
  user: AuthUser | null
  accessToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
}
