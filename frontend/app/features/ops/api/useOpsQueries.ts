import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed } from 'vue'
import { useRuntimeConfig } from '#app'
import { useAuthStore } from '~/entities/user'
import { fetchOpsSummary, retryOpsAnalysis } from './opsApi'

export const opsKeys = {
  all: ['ops'] as const,
  summary: () => [...opsKeys.all, 'summary'] as const
}

export function useOpsQueries() {
  const config = useRuntimeConfig()
  const auth = useAuthStore()
  const queryClient = useQueryClient()
  const isAdmin = computed(() => auth.user?.role === 'ADMIN' || auth.user?.role === 'SUPER_ADMIN')
  const clientOptions = computed(() => ({
    apiBase: config.public.apiBase,
    token: auth.token
  }))

  const summaryQuery = useQuery({
    queryKey: computed(() => opsKeys.summary()),
    enabled: computed(() => Boolean(auth.token) && isAdmin.value),
    queryFn: () => fetchOpsSummary(clientOptions.value),
    refetchInterval: 5000,
    refetchIntervalInBackground: false
  })

  const retryMutation = useMutation({
    mutationFn: (id: string) => retryOpsAnalysis(clientOptions.value, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: opsKeys.summary() })
      queryClient.invalidateQueries({ queryKey: ['analyses'] })
    }
  })

  return {
    isAdmin,
    summaryQuery,
    retryMutation
  }
}
