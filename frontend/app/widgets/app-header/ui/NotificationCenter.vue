<script setup lang="ts">
import { computed, onScopeDispose, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { AppNotification } from '~/entities/notification'
import { useNotificationQueries } from '~/features/notifications/api/useNotificationQueries'

const router = useRouter()
const {
  notificationsQuery,
  markReadMutation,
  markAllReadMutation,
  toast: incomingToast
} = useNotificationQueries()
const isOpen = shallowRef(false)
const toast = shallowRef<AppNotification | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null

const notifications = computed(() => notificationsQuery.data.value ?? [])
const unreadCount = computed(() => notifications.value.filter((item) => !item.readAt).length)
const latestNotifications = computed(() => notifications.value.slice(0, 12))

function showToast(item: AppNotification) {
  toast.value = item
  if (toastTimer) {
    clearTimeout(toastTimer)
  }
  toastTimer = setTimeout(() => {
    toast.value = null
  }, 5200)
}

async function openNotification(item: AppNotification) {
  await markReadMutation.mutateAsync(item.id)
  isOpen.value = false

  if (item.analysisId) {
    await router.push(`/report?id=${item.analysisId}`)
  }
}

async function markAllRead() {
  await markAllReadMutation.mutateAsync()
}

function notificationTone(type: AppNotification['type']) {
  if (type === 'ANALYSIS_FAILED') return 'text-signal'
  if (type === 'ANALYSIS_CANCELLED') return 'text-muted'
  return 'text-steel'
}

watch(incomingToast, (item) => {
  if (item) {
    showToast(item)
  }
})

onScopeDispose(() => {
  if (toastTimer) {
    clearTimeout(toastTimer)
  }
})
</script>

<template>
  <div class="notification-center relative">
    <button
      class="notification-button grid h-10 w-10 place-items-center rounded-[12px] border border-line bg-milk text-sm font-black text-steel transition hover:border-steel hover:bg-white"
      type="button"
      aria-label="Уведомления"
      @click="isOpen = !isOpen"
    >
      <svg
        aria-hidden="true"
        class="h-5 w-5"
        fill="none"
        stroke="currentColor"
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        viewBox="0 0 24 24"
      >
        <path d="M10.3 21a2 2 0 0 0 3.4 0" />
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 7-3 9h18c0-2-3-2-3-9" />
      </svg>
      <span
        v-if="unreadCount"
        class="absolute -right-1 -top-1 min-w-5 rounded-full bg-signal px-1.5 py-0.5 text-[10px] font-black leading-none text-white"
      >
        {{ unreadCount }}
      </span>
    </button>

    <div
      v-if="isOpen"
      class="notification-popover absolute right-0 top-12 z-50 w-[min(360px,calc(100vw-24px))] overflow-hidden rounded-[var(--radius-control)] border border-line bg-paper shadow-soft"
    >
      <div class="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <p class="text-xs font-black uppercase tracking-[0.16em] text-steel">Уведомления</p>
        <button class="text-xs font-bold text-muted transition hover:text-steel" type="button" @click="markAllRead">
          Прочитать все
        </button>
      </div>

      <ul v-if="latestNotifications.length" class="max-h-[420px] overflow-y-auto">
        <li v-for="item in latestNotifications" :key="item.id" class="border-b border-line last:border-b-0">
          <button class="block w-full px-4 py-3 text-left transition hover:bg-milk" type="button" @click="openNotification(item)">
            <span class="flex items-start justify-between gap-3">
              <span :class="['text-sm font-black', notificationTone(item.type)]">{{ item.title }}</span>
              <span v-if="!item.readAt" class="mt-1 h-2 w-2 shrink-0 rounded-full bg-signal" />
            </span>
            <span class="mt-1 block text-xs leading-5 text-muted">{{ item.message }}</span>
          </button>
        </li>
      </ul>

      <p v-else class="px-4 py-6 text-sm font-bold text-muted">Новых уведомлений нет.</p>
    </div>

    <button
      v-if="toast"
      class="notification-toast fixed right-4 top-20 z-50 w-[min(360px,calc(100vw-32px))] rounded-[var(--radius-control)] border border-line bg-paper p-4 text-left shadow-soft"
      type="button"
      @click="openNotification(toast)"
    >
      <span class="block text-sm font-black text-steel">{{ toast.title }}</span>
      <span class="mt-1 block text-xs leading-5 text-muted">{{ toast.message }}</span>
    </button>
  </div>
</template>

<style scoped>
.notification-button,
.notification-popover,
.notification-toast {
  box-shadow: 0 18px 60px rgba(42, 48, 44, 0.14);
}
</style>
