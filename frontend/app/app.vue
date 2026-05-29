<script setup lang="ts">
import { AppHeader } from '~/widgets/app-header'
import { AmbientBackground } from '~/widgets/ambient-background'
</script>

<template>
  <div class="relative min-h-screen overflow-x-hidden">
    <AmbientBackground />
    <AppHeader />
    <main class="relative z-10 min-h-[calc(100vh-73px)]">
      <NuxtPage />
    </main>
  </div>
</template>
