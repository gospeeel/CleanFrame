<script setup lang="ts">
import { computed, watch } from 'vue'
import { navigateTo } from '#app'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '~/entities/user'
import OpsQueuePanel from '~/features/ops/ui/OpsQueuePanel.vue'

const auth = useAuthStore()
const { user, isRestored, isRestoring } = storeToRefs(auth)
const isAdmin = computed(() => user.value?.role === 'ADMIN' || user.value?.role === 'SUPER_ADMIN')
const isReady = computed(() => isRestored.value && !isRestoring.value)

watch(isReady, () => {
  if (isReady.value && !isAdmin.value) {
    navigateTo('/forbidden')
  }
}, { immediate: true })
</script>

<template>
  <OpsQueuePanel v-if="isReady && isAdmin" />
  <section v-else-if="!isReady" class="page-shell max-w-[720px]">
    <div class="glass-panel rounded-[18px] p-6">
      <p class="text-xs font-black uppercase tracking-[0.24em] text-steel">Admin ops</p>
      <h1 class="section-title mt-3 font-display font-semibold text-ink">Проверяем доступ</h1>
      <p class="mt-4 text-sm font-bold leading-7 text-muted">
        Восстанавливаем сессию администратора.
      </p>
    </div>
  </section>
  <section v-else class="page-shell max-w-[720px]">
    <div class="glass-panel rounded-[18px] p-6">
      <p class="text-xs font-black uppercase tracking-[0.24em] text-steel">Admin ops</p>
      <h1 class="section-title mt-3 font-display font-semibold text-ink">Нет доступа</h1>
      <p class="mt-4 text-sm font-bold leading-7 text-muted">
        Этот раздел доступен только администраторам.
      </p>
    </div>
  </section>
</template>
