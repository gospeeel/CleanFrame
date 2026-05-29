<script setup lang="ts">
import { navigateTo } from '#app'
import { onMounted, shallowRef } from 'vue'
import { useAuthStore } from '~/entities/user'

const auth = useAuthStore()
const errorMessage = shallowRef('')

function decodeBase64Url(value: string) {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')
  return atob(padded)
}

onMounted(() => {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  const sessionPayload = params.get('session')

  if (!sessionPayload) {
    errorMessage.value = 'Сервис входа не вернул сессию'
    return
  }

  try {
    const session = JSON.parse(decodeBase64Url(sessionPayload))
    auth.applySession(session)
    void navigateTo('/')
  } catch {
    errorMessage.value = 'Не удалось завершить вход через внешний сервис'
  }
})
</script>

<template>
  <section class="page-shell">
    <div class="glass-panel panel-pad">
      <p class="text-xs font-black uppercase tracking-[0.24em] text-steel">Вход через сервис</p>
      <h1 class="mt-3 font-display text-4xl font-semibold text-ink">Завершаем вход</h1>
      <p class="mt-4 text-sm font-bold text-muted">
        {{ errorMessage || 'Проверяем ответ провайдера...' }}
      </p>
      <NuxtLink
        v-if="errorMessage"
        class="mt-6 inline-flex rounded-[var(--radius-control)] bg-steel px-5 py-3 text-sm font-black uppercase tracking-[0.14em] text-paper"
        to="/login"
      >
        Вернуться ко входу
      </NuxtLink>
    </div>
  </section>
</template>
