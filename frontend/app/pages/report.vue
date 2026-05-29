<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from '#app'
import { storeToRefs } from 'pinia'
import { useAnalysisUiStore } from '~/entities/analysis'
import { UploadPanel, useScriptAnalysis } from '~/features/script-analysis'
import { AnalysisResult } from '~/widgets/analysis-result'

const route = useRoute()
const router = useRouter()
const uiStore = useAnalysisUiStore()
const { selectedFileName } = storeToRefs(uiStore)
const analysis = useScriptAnalysis()

const result = computed(() => analysis.result.value)
const errorMessage = computed(() => {
  if (analysis.data.value?.status === 'FAILED' || analysis.data.value?.status === 'DEAD_LETTER') {
    return analysis.data.value.errorMessage ?? 'Не удалось выполнить анализ'
  }

  const error = analysis.error.value
  if (!error) {
    return ''
  }

  if (typeof error === 'object' && 'data' in error) {
    const payload = error.data as { message?: string; detail?: string } | undefined
    return payload?.message ?? payload?.detail ?? 'Не удалось выполнить анализ'
  }

  return error instanceof Error ? error.message : 'Не удалось выполнить анализ'
})

function handleSubmit(file: File) {
  uiStore.setSelectedFile(file)
  uiStore.showResult()
  void analysis.submit(file)
}

function loadRouteAnalysis() {
  const id = Array.isArray(route.query.id) ? route.query.id[0] : route.query.id
  if (!id) {
    return
  }

  uiStore.showResult()
  void analysis.load(id)
}

onMounted(loadRouteAnalysis)

watch(() => route.query.id, loadRouteAnalysis)

watch(analysis.activeAnalysisId, (id) => {
  if (!id || route.query.id === id) {
    return
  }

  void router.replace({
    path: '/report',
    query: { id }
  })
})
</script>

<template>
  <section class="page-shell">
    <div class="grid gap-6">
      <UploadPanel v-model:selected-file-name="selectedFileName" @submit="handleSubmit" />

      <AnalysisResult
        :result="result"
        :is-pending="analysis.isPending.value"
        :error-message="errorMessage"
      />
    </div>
  </section>
</template>
