import { Injectable, Logger, OnApplicationShutdown, OnModuleInit } from '@nestjs/common'
import { AnalysisStatus, NotificationType } from '@prisma/client'
import { PrismaService } from '../prisma/prisma.service'
import { NotificationsService } from '../notifications/notifications.service'

@Injectable()
export class AnalysisMonitorService implements OnModuleInit, OnApplicationShutdown {
  private readonly logger = new Logger(AnalysisMonitorService.name)
  private timer: ReturnType<typeof setInterval> | null = null

  constructor(
    private readonly prisma: PrismaService,
    private readonly notifications: NotificationsService
  ) {}

  onModuleInit() {
    if (process.env.ANALYSIS_LONG_RUNNING_NOTIFICATIONS_ENABLED === 'false') {
      return
    }

    const intervalMs = Number(process.env.ANALYSIS_LONG_RUNNING_CHECK_INTERVAL_MS ?? 60_000)
    this.timer = setInterval(() => {
      void this.createLongRunningNotifications().catch((error) => {
        this.logger.error('Long-running analysis check failed', error instanceof Error ? error.stack : undefined)
      })
    }, intervalMs)
    this.timer.unref?.()
  }

  async createLongRunningNotifications(now = new Date()) {
    const thresholdMs = Number(process.env.ANALYSIS_LONG_RUNNING_THRESHOLD_MS ?? 10 * 60 * 1000)
    if (!Number.isFinite(thresholdMs) || thresholdMs <= 0) {
      return { created: 0 }
    }

    const cutoff = new Date(now.getTime() - thresholdMs)
    const analyses = await this.prisma.analysis.findMany({
      where: {
        status: { in: [AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING] },
        queuedAt: { lt: cutoff },
        notifications: {
          none: { type: NotificationType.ANALYSIS_LONG_RUNNING }
        }
      },
      select: {
        id: true,
        userId: true,
        fileName: true,
        status: true
      },
      take: 100
    })

    let created = 0
    for (const analysis of analyses) {
      await this.notifications.create({
        userId: analysis.userId,
        type: NotificationType.ANALYSIS_LONG_RUNNING,
        analysisId: analysis.id,
        title: 'Анализ выполняется дольше обычного',
        message: `${analysis.fileName}: задача всё ещё в статусе ${analysis.status}`
      })
      created += 1
    }

    return { created }
  }

  onApplicationShutdown() {
    if (this.timer) {
      clearInterval(this.timer)
    }
  }
}
