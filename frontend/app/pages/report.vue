<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from '#app'
import { storeToRefs } from 'pinia'
import { useAnalysisUiStore } from '~/entities/analysis'
import { UploadPanel, useAnalysisClientOptions, useScriptAnalysis } from '~/features/script-analysis'
import { exportAnalysisPdf } from '~/shared/api/analysisApi'
import { AnalysisResult } from '~/widgets/analysis-result'

const route = useRoute()
const router = useRouter()
const uiStore = useAnalysisUiStore()
const { selectedFileName } = storeToRefs(uiStore)
const analysis = useScriptAnalysis()
const clientOptions = useAnalysisClientOptions()
const isExportingPdf = shallowRef(false)
const exportError = shallowRef('')

const result = computed(() => analysis.result.value)
const currentAnalysisId = computed(() => analysis.activeAnalysisId.value || analysis.data.value?.id || '')
const exportFileName = computed(() => `clean-frame-report-${currentAnalysisId.value.slice(0, 8) || 'analysis'}.pdf`)
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

async function handlePdfExport() {
  if (!currentAnalysisId.value || isExportingPdf.value) {
    return
  }

  isExportingPdf.value = true
  exportError.value = ''

  try {
    const blob = await exportAnalysisPdf(clientOptions.value, currentAnalysisId.value)
    downloadBlob(blob, exportFileName.value)
  } catch (error) {
    exportError.value = error instanceof Error ? error.message : 'Не удалось сформировать PDF'
  } finally {
    isExportingPdf.value = false
  }
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = fileName
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
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

      <div
        v-if="result && currentAnalysisId"
        class="report-actions glass-panel flex flex-wrap items-center justify-between gap-3 px-4 py-3"
      >
        <div>
          <p class="text-xs font-black uppercase tracking-[0.2em] text-steel">Экспорт</p>
          <p class="mt-1 text-sm font-bold text-muted">Сервер сформирует стилизованный PDF и скачает файл.</p>
          <p v-if="exportError" class="mt-1 text-xs font-bold text-signal">{{ exportError }}</p>
        </div>
        <button
          class="report-print-button"
          type="button"
          :disabled="isExportingPdf"
          @click="handlePdfExport"
        >
          {{ isExportingPdf ? 'Готовим PDF' : 'Скачать PDF' }}
        </button>
      </div>

      <AnalysisResult
        :result="result"
        :is-pending="analysis.isPending.value"
        :error-message="errorMessage"
      />
    </div>
  </section>
</template>

<style scoped>
.report-actions {
  border-radius: var(--radius-control);
}

.report-print-button {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(33, 43, 41, 0.12);
  border-radius: 10px;
  background: linear-gradient(135deg, var(--color-blue), #2f5663);
  box-shadow: 0 14px 26px rgba(47, 86, 99, 0.28);
  color: white;
  font-size: 0.8rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  padding: 0 20px;
  text-transform: uppercase;
  transition: box-shadow 160ms ease, filter 160ms ease, transform 160ms ease;
}

.report-print-button:hover {
  filter: brightness(1.05);
  box-shadow: 0 18px 34px rgba(47, 86, 99, 0.34);
  transform: translateY(-1px);
}

.report-print-button:disabled {
  cursor: wait;
  opacity: 0.68;
  transform: none;
}
</style>
