<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import SystemStatePanel from '~/shared/ui/SystemStatePanel.vue'

const route = useRoute()
const loginTarget = computed(() => {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  return redirect ? `/login?redirect=${encodeURIComponent(redirect)}` : '/login'
})
</script>

<template>
  <SystemStatePanel
    eyebrow="Сессия не найдена"
    title="Не авторизован"
    message="Для работы с анализами, историей и отчётами нужно войти в аккаунт."
    code="401"
    :actions="[
      { label: 'Войти', to: loginTarget },
      { label: 'Регистрация', to: '/register', tone: 'secondary' }
    ]"
  />
</template>
