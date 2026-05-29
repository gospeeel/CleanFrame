import { defineStore } from 'pinia'

type ViewMode = 'upload' | 'result'

interface AnalysisUiState {
  selectedFileName: string
  viewMode: ViewMode
  expandedSceneIndexes: number[]
}

export const useAnalysisUiStore = defineStore('analysis-ui', {
  state: (): AnalysisUiState => ({
    selectedFileName: '',
    viewMode: 'upload',
    expandedSceneIndexes: []
  }),
  actions: {
    setSelectedFile(file: File | null) {
      this.selectedFileName = file?.name ?? ''
    },
    showResult() {
      this.viewMode = 'result'
    },
    reset() {
      this.selectedFileName = ''
      this.viewMode = 'upload'
      this.expandedSceneIndexes = []
    },
    toggleScene(index: number) {
      if (this.expandedSceneIndexes.includes(index)) {
        this.expandedSceneIndexes = this.expandedSceneIndexes.filter((item) => item !== index)
        return
      }

      this.expandedSceneIndexes.push(index)
    }
  }
})
