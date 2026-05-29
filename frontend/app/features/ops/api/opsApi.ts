import { authFetch } from '~/shared/api/authFetch'
import type { ApiClientOptions } from '~/shared/api/analysisApi'

export type OpsAnalysisStatus = 'QUEUED' | 'PROCESSING' | 'DONE' | 'FAILED' | 'DEAD_LETTER' | 'CANCELLED'

export interface OpsQueueStatus {
  active: number
  waiting: number
  delayed: number
  failed: number
  completed: number
  concurrency: number
  utilizationPercent: number
}

export interface OpsAnalysisItem {
  id: string
  fileName: string
  status: OpsAnalysisStatus
  maxRating: string | null
  riskCount: number
  reviewCount: number
  createdAt: string
  completedAt: string | null
  queuedAt: string
  startedAt: string | null
  userId: string
  userLogin: string
  userEmail: string
  attempts: number
  queueJobId: string | null
  workerId: string | null
  errorMessage: string | null
  errorCode: string | null
  updatedAt: string
  canRetry: boolean
}

export interface OpsSummary {
  total: number
  queued: number
  processing: number
  done: number
  failed: number
  deadLetter: number
  cancelled: number
  averageQueueLatencyMs: number | null
  averageProcessingTimeMs: number | null
  queue: OpsQueueStatus
  items: OpsAnalysisItem[]
}

export function fetchOpsSummary({ apiBase }: ApiClientOptions) {
  return authFetch<OpsSummary>(`${apiBase}/api/analyses/admin/ops`)
}

export function retryOpsAnalysis({ apiBase }: ApiClientOptions, id: string) {
  return authFetch<{ id: string; status: OpsAnalysisStatus }>(`${apiBase}/api/analyses/admin/ops/${id}/retry`, {
    method: 'POST',
    headers: {
      'x-request-id': createRequestId()
    }
  })
}

function createRequestId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
}
