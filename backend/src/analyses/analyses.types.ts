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

export type AnalysisRecord = Analysis
