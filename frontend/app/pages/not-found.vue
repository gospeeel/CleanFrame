<script setup lang="ts">
import SystemStatePanel from '~/shared/ui/SystemStatePanel.vue'
</script>

<template>
  <SystemStatePanel
    eyebrow="Маршрут не найден"
    title="Страница не найдена"
    message="Такой страницы в Clean Frame нет. Проверьте адрес или вернитесь к анализу сценария."
    code="404"
    :actions="[
      { label: 'К анализу', to: '/report' },
      { label: 'На главную', to: '/', tone: 'secondary' }
    ]"
  />
</template>
