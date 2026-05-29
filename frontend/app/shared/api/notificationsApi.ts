import type { AppNotification } from '~/entities/notification'
import type { ApiClientOptions } from './analysisApi'
import { authFetch } from './authFetch'

export async function fetchNotifications(options: ApiClientOptions, unreadOnly = false) {
  return await authFetch<AppNotification[]>(`${options.apiBase}/api/notifications`, {
    query: { unreadOnly }
  })
}

export async function markNotificationRead(options: ApiClientOptions, id: string) {
  return await authFetch<AppNotification>(`${options.apiBase}/api/notifications/${id}/read`, {
    method: 'PATCH'
  })
}

export async function markAllNotificationsRead(options: ApiClientOptions) {
  return await authFetch<{ ok: true }>(`${options.apiBase}/api/notifications/read-all`, {
    method: 'PATCH'
  })
}
