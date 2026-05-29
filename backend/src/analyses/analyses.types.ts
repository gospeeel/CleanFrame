import { Analysis, AnalysisStatus, Prisma } from '@prisma/client'

export interface AnalysisJobResponse {
  id: string
  status: AnalysisStatus
}

export interface AnalysisListItem {
  id: string
  fileName: string
  status: AnalysisStatus
  maxRating: string | null
  riskCount: number
  reviewCount: number
  createdAt: Date
  completedAt: Date | null
  queuedAt: Date
  startedAt: Date | null
}

export interface AnalysisDetails extends AnalysisListItem {
  processingTime: number | null
  result: Prisma.JsonValue | null
  errorMessage: string | null
  errorCode: string | null
  updatedAt: Date
}

export interface AdminOpsAnalysisItem extends AnalysisListItem {
  userId: string
  userLogin: string
  userEmail: string
  attempts: number
  queueJobId: string | null
  workerId: string | null
  errorMessage: string | null
  errorCode: string | null
  updatedAt: Date
  canRetry: boolean
}

export interface AdminOpsQueueStatus {
  active: number
  waiting: number
  delayed: number
  failed: number
  completed: number
  concurrency: number
  utilizationPercent: number
}

export interface AdminOpsSummary {
  total: number
  queued: number
  processing: number
  done: number
  failed: number
  deadLetter: number
  cancelled: number
  averageQueueLatencyMs: number | null
  averageProcessingTimeMs: number | null
  queue: AdminOpsQueueStatus
  items: AdminOpsAnalysisItem[]
}

export type AnalysisRecord = Analysis
