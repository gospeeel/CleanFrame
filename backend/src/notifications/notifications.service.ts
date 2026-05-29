import { Injectable, NotFoundException } from '@nestjs/common'
import { ConfigService } from '@nestjs/config'
import IORedis from 'ioredis'
import { PrismaService } from '../prisma/prisma.service'
import { CreateNotificationInput, NotificationDto, NotificationRecord } from './notifications.types'

@Injectable()
export class NotificationsService {
  private readonly channelPrefix = 'notifications:user:'

  constructor(
    private readonly prisma: PrismaService,
    private readonly configService: ConfigService
  ) {}

  async create(input: CreateNotificationInput) {
    const notification = await this.prisma.notification.create({
      data: {
        userId: input.userId,
        type: input.type,
        title: input.title,
        message: input.message,
        analysisId: input.analysisId ?? null
      }
    })

    await this.publish(notification)
    return notification
  }

  async list(userId: string, unreadOnly = false): Promise<NotificationDto[]> {
    const notifications = await this.prisma.notification.findMany({
      where: {
        userId,
        ...(unreadOnly ? { readAt: null } : {})
      },
      orderBy: { createdAt: 'desc' },
      take: 50
    })

    return notifications.map((notification) => this.toDto(notification))
  }

  async markRead(userId: string, id: string): Promise<NotificationDto> {
    const notification = await this.prisma.notification.findFirst({
      where: {
        id,
        userId
      }
    })

    if (!notification) {
      throw new NotFoundException('Уведомление не найдено')
    }

    const updated = await this.prisma.notification.update({
      where: { id },
      data: { readAt: notification.readAt ?? new Date() }
    })

    return this.toDto(updated)
  }

  async markAllRead(userId: string) {
    await this.prisma.notification.updateMany({
      where: {
        userId,
        readAt: null
      },
      data: { readAt: new Date() }
    })

    return { ok: true }
  }

  private toDto(notification: NotificationRecord): NotificationDto {
    return {
      id: notification.id,
      type: notification.type,
      title: notification.title,
      message: notification.message,
      analysisId: notification.analysisId,
      readAt: notification.readAt,
      createdAt: notification.createdAt
    }
  }

  createSubscriber() {
    const redisUrl = this.configService.get<string>('REDIS_URL') ?? 'redis://127.0.0.1:6379'
    return new IORedis(redisUrl, { lazyConnect: true, maxRetriesPerRequest: null })
  }

  channelForUser(userId: string) {
    return `${this.channelPrefix}${userId}`
  }

  private async publish(notification: NotificationRecord) {
    const redis = this.createSubscriber()
    try {
      await redis.connect()
      await redis.publish(this.channelForUser(notification.userId), JSON.stringify(this.toDto(notification)))
    } finally {
      redis.disconnect()
    }
  }
}
