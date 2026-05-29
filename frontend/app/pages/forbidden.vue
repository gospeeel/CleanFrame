<script setup lang="ts">
import SystemStatePanel from '~/shared/ui/SystemStatePanel.vue'
</script>

<template>
  <SystemStatePanel
    eyebrow="Доступ ограничен"
    title="Недостаточно прав"
    message="Этот раздел доступен только администраторам. Если вам нужен доступ к операционным или супер-админским функциям, обратитесь к главному администратору проекта."
    code="403"
    :actions="[
      { label: 'Вернуться', to: '/' },
      { label: 'Профиль', to: '/profile', tone: 'secondary' }
    ]"
  />
</template>
