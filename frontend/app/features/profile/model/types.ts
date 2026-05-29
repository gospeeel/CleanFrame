import type { AuthResponse, UserRole, UserSession } from '~/entities/user'

export interface AdminUser {
  id: string
  login: string
  email: string
  emailVerifiedAt?: string | null
  avatarUrl?: string | null
  role: UserRole
  isActive: boolean
  createdAt: string
  accounts: Array<{ provider: string }>
  canChangeRole: boolean
  canBan: boolean
  canUnban: boolean
  canDelete: boolean
}

export interface InviteResponse {
  id: string
  role: UserRole
  token: string
  expiresAt: string
  createdAt: string
}

export interface RequestEmailChangePayload {
  email: string
}

export interface ConfirmEmailChangePayload {
  email: string
  code: string
}

export interface ChangePasswordPayload {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

export type { AuthResponse, UserRole, UserSession }
