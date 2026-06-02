import type { AnalysisDetails, AnalysisJobResponse, AnalysisListItem, AnalysisTargetRating } from '~/entities/analysis'
import { authFetch } from './authFetch'

export interface ApiClientOptions {
  apiBase: string
  token: string
}

export async function createAnalysis(options: ApiClientOptions, file: File, targetRating: AnalysisTargetRating = 'raw') {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('targetRating', targetRating)

  return await authFetch<AnalysisJobResponse>(`${options.apiBase}/api/analyses`, {
    method: 'POST',
    body: formData,
    headers: {
      'x-request-id': createRequestId()
    }
  })
}

export async function fetchAnalyses(options: ApiClientOptions) {
  return await authFetch<AnalysisListItem[]>(`${options.apiBase}/api/analyses`)
}

export async function fetchAnalysis(options: ApiClientOptions, id: string) {
  return await authFetch<AnalysisDetails>(`${options.apiBase}/api/analyses/${id}`)
}

export async function exportAnalysisPdf(options: ApiClientOptions, id: string) {
  return await authFetch<Blob>(`${options.apiBase}/api/analyses/${id}/export/pdf`, {
    responseType: 'blob'
  })
}

export async function retryAnalysis(options: ApiClientOptions, id: string) {
  return await authFetch<AnalysisJobResponse>(`${options.apiBase}/api/analyses/${id}/retry`, {
    method: 'POST',
    headers: {
      'x-request-id': createRequestId()
    }
  })
}

export async function cancelAnalysis(options: ApiClientOptions, id: string) {
  return await authFetch<AnalysisDetails>(`${options.apiBase}/api/analyses/${id}/cancel`, {
    method: 'POST',
    headers: {
      'x-request-id': createRequestId()
    }
  })
}

function createRequestId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
}
