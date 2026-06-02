import { computed } from 'vue'
import { useActiveAnalysisQuery } from './useAnalysisQueries'

export function useScriptAnalysis() {
  const analysis = useActiveAnalysisQuery()

  const data = computed(() => analysis.detailsQuery.data.value ?? null)
  const error = computed(() =>
    analysis.uploadMutation.error.value
    ?? analysis.detailsQuery.error.value
    ?? analysis.retryMutation.error.value
    ?? analysis.cancelMutation.error.value
    ?? null
  )
  const isPending = computed(() => {
    const status = data.value?.status
    return analysis.uploadMutation.isPending.value
      || analysis.detailsQuery.isLoading.value
      || status === 'QUEUED'
      || status === 'PROCESSING'
  })
  const result = computed(() => data.value?.result ?? null)

  return {
    activeAnalysisId: analysis.activeAnalysisId,
    data,
    error,
    isPending,
    result,
    submit: analysis.submit,
    load: analysis.load,
    reset: analysis.reset,
    retryMutation: analysis.retryMutation,
    cancelMutation: analysis.cancelMutation
  }
}
