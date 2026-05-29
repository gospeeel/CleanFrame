import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, onScopeDispose, shallowRef, watch } from 'vue'
import { useRuntimeConfig } from '#app'
import { useAuthStore } from '~/entities/user'
import type { AppNotification } from '~/entities/notification'
import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from '~/shared/api'

export const notificationKeys = {
  all: ['notifications'] as const,
  list: () => [...notificationKeys.all, 'list'] as const
}

export function useNotificationQueries() {
  const config = useRuntimeConfig()
  const auth = useAuthStore()
  const queryClient = useQueryClient()
  const toast = shallowRef<AppNotification | null>(null)
  const streamConnected = shallowRef(false)
  const knownIds = new Set<string>()
  let abortController: AbortController | null = null

  const notificationsQuery = useQuery({
    queryKey: computed(() => notificationKeys.list()),
    enabled: computed(() => Boolean(auth.token)),
    queryFn: () => fetchNotifications({
      apiBase: config.public.apiBase,
      token: auth.token
    }, false),
    refetchInterval: computed(() => streamConnected.value ? false : 20_000),
    refetchIntervalInBackground: false,
    staleTime: 15_000
  })

  const markReadMutation = useMutation({
    mutationFn: (id: string) => markNotificationRead({
      apiBase: config.public.apiBase,
      token: auth.token
    }, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationKeys.list() })
  })

  const markAllReadMutation = useMutation({
    mutationFn: () => markAllNotificationsRead({
      apiBase: config.public.apiBase,
      token: auth.token
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationKeys.list() })
  })

  watch(
    () => notificationsQuery.data.value,
    (items) => {
      if (!items) {
        return
      }

      const unseen = items.filter((item) => !knownIds.has(item.id) && !item.readAt)
      items.forEach((item) => knownIds.add(item.id))

      if (knownIds.size > unseen.length) {
        toast.value = unseen[0] ?? null
      }
    }
  )

  watch(
    () => auth.token,
    (token) => {
      abortController?.abort()
      streamConnected.value = false

      if (!token || !process.client) {
        return
      }

      abortController = new AbortController()
      void connectNotificationStream({
        apiBase: config.public.apiBase,
        token,
        signal: abortController.signal,
        onOpen: () => {
          streamConnected.value = true
        },
        onClose: () => {
          streamConnected.value = false
        },
        onNotification: (notification) => {
          knownIds.add(notification.id)
          queryClient.setQueryData<AppNotification[]>(notificationKeys.list(), (current) => {
            const existing = current ?? []
            const filtered = existing.filter((item) => item.id !== notification.id)
            return [notification, ...filtered].slice(0, 50)
          })
          if (!notification.readAt) {
            toast.value = notification
          }
        }
      })
    },
    { immediate: true }
  )

  onScopeDispose(() => {
    abortController?.abort()
  })

  return {
    notificationsQuery,
    markReadMutation,
    markAllReadMutation,
    toast
  }
}

async function connectNotificationStream(options: {
  apiBase: string
  token: string
  signal: AbortSignal
  onOpen: () => void
  onClose: () => void
  onNotification: (notification: AppNotification) => void
}) {
  try {
    const response = await fetch(`${options.apiBase}/api/notifications/stream`, {
      headers: {
        Accept: 'text/event-stream',
        Authorization: `Bearer ${options.token}`
      },
      signal: options.signal
    })

    if (!response.ok || !response.body) {
      options.onClose()
      return
    }

    options.onOpen()
    await readSseStream(response.body, options.onNotification, options.signal)
  } catch (error) {
    if (!options.signal.aborted) {
      options.onClose()
    }
  } finally {
    options.onClose()
  }
}

async function readSseStream(
  body: ReadableStream<Uint8Array>,
  onNotification: (notification: AppNotification) => void,
  signal: AbortSignal
) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (!signal.aborted) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split('\n\n')
      buffer = events.pop() ?? ''

      for (const rawEvent of events) {
        const event = parseSseEvent(rawEvent)
        if (event.name !== 'notification' || !event.data) {
          continue
        }

        onNotification(JSON.parse(event.data) as AppNotification)
      }
    }
  } finally {
    reader.releaseLock()
  }
}

function parseSseEvent(rawEvent: string) {
  let name = 'message'
  const data: string[] = []

  for (const line of rawEvent.split('\n')) {
    if (line.startsWith('event:')) {
      name = line.slice('event:'.length).trim()
    }
    if (line.startsWith('data:')) {
      data.push(line.slice('data:'.length).trim())
    }
  }

  return {
    name,
    data: data.join('\n')
  }
}
