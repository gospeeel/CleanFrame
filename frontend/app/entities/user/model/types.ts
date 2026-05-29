export type UserRole = 'ANALYST' | 'ADMIN' | 'SUPER_ADMIN'
export type AuthProvider = 'credentials' | 'google' | 'yandex' | 'vk'

export interface UserSession {
  id: string
  login: string
  email: string
  emailVerifiedAt?: string | null
  avatarUrl?: string | null
  role: UserRole
  isActive: boolean
  provider?: AuthProvider
  createdAt?: string
}

export interface AuthResponse {
  accessToken: string
  refreshToken: string
  expiresIn: number
  user: UserSession
}
