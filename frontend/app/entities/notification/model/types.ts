export type NotificationType =
  | 'ANALYSIS_DONE'
  | 'ANALYSIS_FAILED'
  | 'ANALYSIS_LONG_RUNNING'
  | 'ANALYSIS_CANCELLED'

export interface AppNotification {
  id: string
  type: NotificationType
  title: string
  message: string
  analysisId: string | null
  readAt: string | null
  createdAt: string
}
