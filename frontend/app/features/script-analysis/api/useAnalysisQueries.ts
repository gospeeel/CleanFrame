import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, nextTick, shallowRef } from 'vue'
import { useRuntimeConfig } from '#app'
import { useAuthStore } from '~/entities/user'
import type { AnalysisDetails } from '~/entities/analysis'
import {
  cancelAnalysis,
  createAnalysis,
  fetchAnalyses,
  fetchAnalysis,
  retryAnalysis
} from '~/shared/api/analysisApi'

export const analysisKeys = {
  all: ['analyses'] as const,
  list: () => [...analysisKeys.all, 'list'] as const,
  detail: (id: string) => [...analysisKeys.all, 'detail', id] as const
}

function isTerminal(status?: AnalysisDetails['status']) {
  return status === 'DONE' || status === 'FAILED' || status === 'DEAD_LETTER' || status === 'CANCELLED'
}

export function useAnalysisClientOptions() {
  const config = useRuntimeConfig()
  const auth = useAuthStore()

  return computed(() => ({
    apiBase: config.public.apiBase,
    token: auth.token
  }))
}

export function useAnalysisListQuery() {
  const auth = useAuthStore()
  const clientOptions = useAnalysisClientOptions()

  return useQuery({
    queryKey: computed(() => analysisKeys.list()),
    enabled: computed(() => Boolean(auth.token)),
    queryFn: () => fetchAnalyses(clientOptions.value),
    staleTime: 10_000
  })
}

export function useAnalysisDetailsQuery(id: () => string) {
  const auth = useAuthStore()
  const clientOptions = useAnalysisClientOptions()

  return useQuery({
    queryKey: computed(() => analysisKeys.detail(id())),
    enabled: computed(() => Boolean(auth.token) && Boolean(id())),
    queryFn: () => fetchAnalysis(clientOptions.value, id()),
    refetchInterval: (query) => {
      const status = (query.state.data as AnalysisDetails | undefined)?.status
      return status && !isTerminal(status) ? 2000 : false
    },
    refetchIntervalInBackground: false
  })
}

export function useAnalysisMutations() {
  const queryClient = useQueryClient()
  const clientOptions = useAnalysisClientOptions()

  const uploadMutation = useMutation({
    mutationFn: (file: File) => createAnalysis(clientOptions.value, file),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: analysisKeys.list() })
      queryClient.invalidateQueries({ queryKey: analysisKeys.detail(job.id) })
    }
  })

  const retryMutation = useMutation({
    mutationFn: (id: string) => retryAnalysis(clientOptions.value, id),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: analysisKeys.list() })
      queryClient.invalidateQueries({ queryKey: analysisKeys.detail(job.id) })
    }
  })

  const cancelMutation = useMutation({
    mutationFn: (id: string) => cancelAnalysis(clientOptions.value, id),
    onSuccess: (analysis) => {
      queryClient.invalidateQueries({ queryKey: analysisKeys.list() })
      queryClient.setQueryData(analysisKeys.detail(analysis.id), analysis)
    }
  })

  return {
    uploadMutation,
    retryMutation,
    cancelMutation
  }
}

export function useActiveAnalysisQuery() {
  const activeAnalysisId = shallowRef('')
  const detailsQuery = useAnalysisDetailsQuery(() => activeAnalysisId.value)
  const mutations = useAnalysisMutations()

  async function submit(file: File) {
    activeAnalysisId.value = ''
    const job = await mutations.uploadMutation.mutateAsync(file)
    activeAnalysisId.value = job.id
    await nextTick()
    await detailsQuery.refetch()
    return job
  }

  async function load(id: string) {
    activeAnalysisId.value = id
    await nextTick()
    await detailsQuery.refetch()
  }

  return {
    activeAnalysisId,
    detailsQuery,
    submit,
    load,
    ...mutations
  }
}
