import { Injectable, Logger, OnApplicationShutdown, OnModuleInit } from '@nestjs/common'
import { AnalysisStatus } from '@prisma/client'
import { PrismaService } from '../prisma/prisma.service'
import { AnalysisFileStorageService } from './analysis-file-storage.service'

@Injectable()
export class AnalysisRetentionService implements OnModuleInit, OnApplicationShutdown {
  private readonly logger = new Logger(AnalysisRetentionService.name)
  private timer: ReturnType<typeof setInterval> | null = null

  constructor(
    private readonly prisma: PrismaService,
    private readonly fileStorage: AnalysisFileStorageService
  ) {}

  onModuleInit() {
    if (process.env.ANALYSIS_RETENTION_CLEANUP_ENABLED === 'false') {
      return
    }

    const intervalMs = Number(process.env.ANALYSIS_RETENTION_CLEANUP_INTERVAL_MS ?? 60 * 60 * 1000)
    this.timer = setInterval(() => {
      void this.cleanupExpiredSourceFiles().catch((error) => {
        this.logger.error('Analysis retention cleanup failed', error instanceof Error ? error.stack : undefined)
      })
    }, intervalMs)
    this.timer.unref?.()
  }

  async cleanupExpiredSourceFiles(now = new Date()) {
    const retentionDays = Number(process.env.ANALYSIS_FAILED_FILE_RETENTION_DAYS ?? '7')
    if (!Number.isFinite(retentionDays) || retentionDays < 0) {
      return { removed: 0 }
    }

    const cutoff = new Date(now.getTime() - retentionDays * 24 * 60 * 60 * 1000)
    const analyses = await this.prisma.analysis.findMany({
      where: {
        status: { in: [AnalysisStatus.FAILED, AnalysisStatus.DEAD_LETTER, AnalysisStatus.CANCELLED] },
        completedAt: { lt: cutoff },
        sourceFilePath: { not: null }
      },
      select: {
        id: true,
        sourceFilePath: true
      },
      take: 100
    })

    let removed = 0
    for (const analysis of analyses) {
      await this.fileStorage.remove(analysis.sourceFilePath)
      await this.prisma.analysis.update({
        where: { id: analysis.id },
        data: { sourceFilePath: null }
      })
      removed += 1
    }

    if (removed > 0) {
      this.logger.log(`Removed ${removed} retained analysis source files`)
    }

    return { removed }
  }

  onApplicationShutdown() {
    if (this.timer) {
      clearInterval(this.timer)
    }
  }
}
