import type {
  AdminUser,
  AuthResponse,
  ChangePasswordPayload,
  ConfirmEmailChangePayload,
  InviteResponse,
  RequestEmailChangePayload,
  UserRole,
  UserSession
} from '../model/types'
import { authFetch } from '~/shared/api/authFetch'

interface ApiClientOptions {
  apiBase: string
  token: string
}

export function fetchAdminUsers({ apiBase, token }: ApiClientOptions) {
  void token
  return authFetch<AdminUser[]>(`${apiBase}/api/auth/admin/users`)
}

export function createAdminInvite({ apiBase, token }: ApiClientOptions, expiresInHours: number) {
  void token
  return authFetch<InviteResponse>(`${apiBase}/api/auth/admin/invites`, {
    method: 'POST',
    body: {
      role: 'ADMIN' satisfies UserRole,
      expiresInHours
    }
  })
}

export function updateUserRole({ apiBase, token }: ApiClientOptions, userId: string, role: UserRole) {
  void token
  return authFetch<AdminUser>(`${apiBase}/api/auth/admin/users/${userId}/role`, {
    method: 'PATCH',
    body: { role }
  })
}

export function banUser({ apiBase, token }: ApiClientOptions, userId: string) {
  void token
  return authFetch<AdminUser>(`${apiBase}/api/auth/admin/users/${userId}/ban`, {
    method: 'PATCH'
  })
}

export function unbanUser({ apiBase, token }: ApiClientOptions, userId: string) {
  void token
  return authFetch<AdminUser>(`${apiBase}/api/auth/admin/users/${userId}/unban`, {
    method: 'PATCH'
  })
}

export function deleteUser({ apiBase, token }: ApiClientOptions, userId: string) {
  void token
  return authFetch<{ ok: boolean }>(`${apiBase}/api/auth/admin/users/${userId}`, {
    method: 'DELETE'
  })
}

export function requestEmailChange({ apiBase, token }: ApiClientOptions, payload: RequestEmailChangePayload) {
  void token
  return authFetch<{ ok: boolean }>(`${apiBase}/api/auth/profile/email/request-code`, {
    method: 'POST',
    body: payload
  })
}

export function confirmEmailChange({ apiBase, token }: ApiClientOptions, payload: ConfirmEmailChangePayload) {
  void token
  return authFetch<AuthResponse>(`${apiBase}/api/auth/profile/email/confirm`, {
    method: 'POST',
    body: payload
  })
}

export function changePassword({ apiBase, token }: ApiClientOptions, payload: ChangePasswordPayload) {
  void token
  return authFetch<{ ok: boolean }>(`${apiBase}/api/auth/profile/password`, {
    method: 'PATCH',
    body: payload
  })
}

export function uploadAvatar({ apiBase, token }: ApiClientOptions, file: File) {
  void token
  const formData = new FormData()
  formData.append('avatar', file)

  return authFetch<UserSession>(`${apiBase}/api/auth/profile/avatar`, {
    method: 'POST',
    body: formData
  })
}

export function deleteAvatar({ apiBase, token }: ApiClientOptions) {
  void token
  return authFetch<UserSession>(`${apiBase}/api/auth/profile/avatar`, {
    method: 'DELETE'
  })
}
