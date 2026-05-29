import { Notification, NotificationType } from '@prisma/client'

export interface CreateNotificationInput {
  userId: string
  type: NotificationType
  title: string
  message: string
  analysisId?: string | null
}

export interface NotificationDto {
  id: string
  type: NotificationType
  title: string
  message: string
  analysisId: string | null
  readAt: Date | null
  createdAt: Date
}

export type NotificationRecord = Notification
