import { useQuery } from '@tanstack/vue-query'
import { computed, shallowRef, watch } from 'vue'
import type { AnalysisDetails, AnalysisListItem } from '~/entities/analysis'
import { useAnalysisClientOptions, useAnalysisListQuery } from '~/features/script-analysis'
import { fetchAnalysis } from '~/shared/api/analysisApi'

export interface AnalysisGroup {
  fileName: string
  analyses: AnalysisListItem[]
}

export function useCompareQueries() {
  const listQuery = useAnalysisListQuery()
  const clientOptions = useAnalysisClientOptions()
  const selectedFileName = shallowRef('')
  const selectedIds = shallowRef<string[]>([])

  const groups = computed<AnalysisGroup[]>(() => {
    const grouped = new Map<string, AnalysisListItem[]>()
    for (const analysis of listQuery.data.value ?? []) {
      const items = grouped.get(analysis.fileName) ?? []
      items.push(analysis)
      grouped.set(analysis.fileName, items)
    }

    return Array.from(grouped.entries())
      .map(([fileName, analyses]) => ({
        fileName,
        analyses: analyses.sort((left, right) =>
          new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()
        )
      }))
      .filter((group) => group.analyses.length > 1)
      .sort((left, right) => right.analyses.length - left.analyses.length)
  })

  const selectedGroup = computed(() =>
    groups.value.find((group) => group.fileName === selectedFileName.value) ?? groups.value[0] ?? null
  )

  watch(groups, (nextGroups) => {
    if (!selectedFileName.value && nextGroups[0]) {
      selectedFileName.value = nextGroups[0].fileName
    }
  }, { immediate: true })

  watch(selectedGroup, (group) => {
    selectedIds.value = group?.analyses.slice(0, 2).map((analysis) => analysis.id) ?? []
  }, { immediate: true })

  const detailsQuery = useQuery({
    queryKey: computed(() => ['compare', selectedIds.value]),
    enabled: computed(() => selectedIds.value.length >= 2),
    queryFn: async () => {
      const details = await Promise.all(
        selectedIds.value.map((id) => fetchAnalysis(clientOptions.value, id))
      )
      return details
    },
    staleTime: 10_000
  })

  function toggleAnalysis(id: string) {
    if (selectedIds.value.includes(id)) {
      selectedIds.value = selectedIds.value.filter((item) => item !== id)
      return
    }

    selectedIds.value = [...selectedIds.value, id]
  }

  return {
    listQuery,
    groups,
    selectedFileName,
    selectedIds,
    selectedGroup,
    detailsQuery: detailsQuery as typeof detailsQuery & { data: typeof detailsQuery.data & { value: AnalysisDetails[] | undefined } },
    toggleAnalysis
  }
}
