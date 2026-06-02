import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common'
import { AnalysisStatus, NotificationType } from '@prisma/client'
import { AUDIT_ACTIONS, AuditLogService } from '../audit/audit-log.service'
import { NotificationsService } from '../notifications/notifications.service'
import { PrismaService } from '../prisma/prisma.service'
import { AnalysisFileStorageService } from './analysis-file-storage.service'
import { AnalysisQueueService } from './analysis-queue.service'
import {
  AdminOpsAnalysisItem,
  AdminOpsSummary,
  AnalysisDetails,
  AnalysisJobResponse,
  AnalysisListItem,
  AnalysisRecord
} from './analyses.types'

@Injectable()
export class AnalysesService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly fileStorage: AnalysisFileStorageService,
    private readonly queue: AnalysisQueueService,
    private readonly notifications: NotificationsService,
    private readonly auditLog: AuditLogService
  ) {}

  async create(
    userId: string,
    file: Express.Multer.File,
    requestId?: string,
    rawTargetRating?: string
  ): Promise<AnalysisJobResponse> {
    const targetRating = this.normalizeTargetRating(rawTargetRating)
    const analysis = await this.prisma.analysis.create({
      data: {
        userId,
        fileName: file.originalname,
        targetRating,
        status: AnalysisStatus.QUEUED
      }
    })

    const savedFile = await this.fileStorage.save(analysis.id, file)
    await this.prisma.analysis.update({
      where: { id: analysis.id },
      data: {
        fileName: savedFile.fileName,
        sourceFilePath: savedFile.filePath
      }
    })

    const queueJobId = await this.queue.enqueue({ analysisId: analysis.id, userId, requestId })

    await this.prisma.analysis.update({
      where: { id: analysis.id },
      data: {
        queueJobId
      }
    })
    await this.auditLog.record({
      action: AUDIT_ACTIONS.ANALYSIS_CREATED,
      userId,
      analysisId: analysis.id,
      metadata: {
        queueJobId,
        targetRating,
        fileExtension: this.getExtension(savedFile.fileName),
        mimeType: savedFile.mimeType
      }
    })

    return {
      id: analysis.id,
      status: analysis.status,
      targetRating
    }
  }

  async list(userId: string): Promise<AnalysisListItem[]> {
    const analyses = await this.prisma.analysis.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      take: 50
    })

    return analyses.map((analysis) => this.toListItem(analysis))
  }

  async get(userId: string, id: string): Promise<AnalysisDetails> {
    const analysis = await this.prisma.analysis.findFirst({
      where: {
        id,
        userId
      }
    })

    if (!analysis) {
      throw new NotFoundException('Анализ не найден')
    }

    return this.toDetails(analysis)
  }

  async retry(userId: string, id: string, requestId?: string): Promise<AnalysisJobResponse> {
    const analysis = await this.getOwnedAnalysis(userId, id)

    if (
      analysis.status !== AnalysisStatus.FAILED &&
      analysis.status !== AnalysisStatus.DEAD_LETTER &&
      analysis.status !== AnalysisStatus.CANCELLED
    ) {
      throw new BadRequestException('Повторный запуск доступен только для ошибочных, dead-letter или отменённых анализов')
    }

    if (!analysis.sourceFilePath) {
      throw new BadRequestException('Исходный файл уже удалён. Загрузите файл заново.')
    }

    const queueJobId = await this.queue.enqueue({ analysisId: analysis.id, userId, requestId })
    const updated = await this.prisma.analysis.update({
      where: { id: analysis.id },
      data: {
        status: AnalysisStatus.QUEUED,
        queueJobId,
        queuedAt: new Date(),
        startedAt: null,
        completedAt: null,
        errorCode: null,
        errorMessage: null
      }
    })

    return {
      id: updated.id,
      status: updated.status,
      targetRating: updated.targetRating
    }
  }

  async adminOpsSummary(): Promise<AdminOpsSummary> {
    const problemCutoff = this.opsProblemCutoff()
    const visibleOpsWhere = {
      OR: [
        {
          status: {
            in: [AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING]
          }
        },
        {
          status: {
            in: [AnalysisStatus.FAILED, AnalysisStatus.DEAD_LETTER]
          },
          updatedAt: {
            gte: problemCutoff
          },
          NOT: {
            errorCode: 'BENCHMARK_TIMEOUT'
          }
        }
      ]
    }
    const [total, byStatus, activeItems, completedForAverages, queue] = await Promise.all([
      this.prisma.analysis.count(),
      this.prisma.analysis.groupBy({
        where: visibleOpsWhere,
        by: ['status'],
        _count: { _all: true }
      }),
      this.prisma.analysis.findMany({
        where: visibleOpsWhere,
        include: {
          user: {
            select: {
              id: true,
              login: true,
              email: true
            }
          }
        },
        orderBy: [
          { status: 'asc' },
          { updatedAt: 'desc' }
        ],
        take: 100
      }),
      this.prisma.analysis.findMany({
        where: {
          startedAt: { not: null },
          completedAt: { not: null }
        },
        select: {
          queuedAt: true,
          startedAt: true,
          completedAt: true
        },
        orderBy: { completedAt: 'desc' },
        take: 200
      }),
      this.queue.getStatus()
    ])

    const statusCounts = new Map(byStatus.map((item) => [item.status, item._count._all]))
    const queueLatencies = completedForAverages
      .map((item) => item.startedAt ? item.startedAt.getTime() - item.queuedAt.getTime() : null)
      .filter((value): value is number => value !== null && value >= 0)
    const processingTimes = completedForAverages
      .map((item) => item.startedAt && item.completedAt ? item.completedAt.getTime() - item.startedAt.getTime() : null)
      .filter((value): value is number => value !== null && value >= 0)

    return {
      total,
      queued: statusCounts.get(AnalysisStatus.QUEUED) ?? 0,
      processing: statusCounts.get(AnalysisStatus.PROCESSING) ?? 0,
      done: statusCounts.get(AnalysisStatus.DONE) ?? 0,
      failed: statusCounts.get(AnalysisStatus.FAILED) ?? 0,
      deadLetter: statusCounts.get(AnalysisStatus.DEAD_LETTER) ?? 0,
      cancelled: statusCounts.get(AnalysisStatus.CANCELLED) ?? 0,
      averageQueueLatencyMs: this.average(queueLatencies),
      averageProcessingTimeMs: this.average(processingTimes),
      queue,
      items: activeItems.map((analysis) => this.toAdminOpsItem(analysis))
    }
  }

  async retryAsAdmin(id: string, requestId?: string): Promise<AnalysisJobResponse> {
    const analysis = await this.prisma.analysis.findUnique({ where: { id } })

    if (!analysis) {
      throw new NotFoundException('Анализ не найден')
    }

    if (analysis.status !== AnalysisStatus.FAILED && analysis.status !== AnalysisStatus.DEAD_LETTER) {
      throw new BadRequestException('Ручной retry доступен только для FAILED или DEAD_LETTER')
    }

    if (!analysis.sourceFilePath) {
      throw new BadRequestException('Исходный файл уже удалён. Нужно загрузить файл заново.')
    }

    const queueJobId = await this.queue.enqueue({ analysisId: analysis.id, userId: analysis.userId, requestId })
    const updated = await this.prisma.analysis.update({
      where: { id: analysis.id },
      data: {
        status: AnalysisStatus.QUEUED,
        queueJobId,
        queuedAt: new Date(),
        startedAt: null,
        completedAt: null,
        errorCode: null,
        errorMessage: null
      }
    })

    return {
      id: updated.id,
      status: updated.status,
      targetRating: updated.targetRating
    }
  }

  async cancel(userId: string, id: string): Promise<AnalysisDetails> {
    const analysis = await this.getOwnedAnalysis(userId, id)

    if (analysis.status !== AnalysisStatus.QUEUED) {
      throw new BadRequestException('Отменить можно только анализ в очереди')
    }

    await this.queue.remove(analysis.queueJobId)
    await this.fileStorage.remove(analysis.sourceFilePath)

    const updated = await this.prisma.analysis.update({
      where: { id: analysis.id },
      data: {
        status: AnalysisStatus.CANCELLED,
        errorCode: null,
        errorMessage: 'Анализ отменён пользователем',
        sourceFilePath: null,
        completedAt: new Date()
      }
    })
    await this.auditLog.record({
      action: AUDIT_ACTIONS.ANALYSIS_CANCELLED,
      userId,
      analysisId: analysis.id,
      metadata: { queueJobId: analysis.queueJobId }
    })
    await this.auditLog.record({
      action: AUDIT_ACTIONS.SOURCE_FILE_REMOVED,
      userId,
      analysisId: analysis.id,
      metadata: { reason: 'cancelled' }
    })

    await this.notifications.create({
      userId,
      type: NotificationType.ANALYSIS_CANCELLED,
      analysisId: analysis.id,
      title: 'Анализ отменён',
      message: `${analysis.fileName}: задача удалена из очереди`
    })

    return this.toDetails(updated)
  }

  private async getOwnedAnalysis(userId: string, id: string) {
    const analysis = await this.prisma.analysis.findFirst({
      where: {
        id,
        userId
      }
    })

    if (!analysis) {
      throw new NotFoundException('Анализ не найден')
    }

    return analysis
  }

  private toListItem(analysis: AnalysisRecord): AnalysisListItem {
    return {
      id: analysis.id,
      fileName: analysis.fileName,
      status: analysis.status,
      maxRating: analysis.maxRating,
      targetRating: analysis.targetRating,
      riskCount: analysis.riskCount,
      reviewCount: analysis.reviewCount,
      createdAt: analysis.createdAt,
      completedAt: analysis.completedAt,
      queuedAt: analysis.queuedAt,
      startedAt: analysis.startedAt
    }
  }

  private toDetails(analysis: AnalysisRecord): AnalysisDetails {
    return {
      ...this.toListItem(analysis),
      processingTime: analysis.processingTime,
      result: analysis.resultJson,
      errorMessage: analysis.errorMessage,
      errorCode: analysis.errorCode,
      updatedAt: analysis.updatedAt
    }
  }

  private toAdminOpsItem(
    analysis: AnalysisRecord & { user: { id: string; login: string; email: string } }
  ): AdminOpsAnalysisItem {
    const privacyMode = process.env.PRIVACY_MODE === 'true'
    return {
      ...this.toListItem(analysis),
      fileName: privacyMode ? this.privateFileLabel(analysis.id) : analysis.fileName,
      userId: analysis.user.id,
      userLogin: privacyMode ? this.privateUserLabel(analysis.user.id) : analysis.user.login,
      userEmail: privacyMode ? '[filtered]' : analysis.user.email,
      attempts: analysis.attempts,
      queueJobId: analysis.queueJobId,
      workerId: analysis.workerId,
      errorMessage: analysis.errorMessage,
      errorCode: analysis.errorCode,
      updatedAt: analysis.updatedAt,
      canRetry: analysis.status === AnalysisStatus.FAILED || analysis.status === AnalysisStatus.DEAD_LETTER
    }
  }

  private average(values: number[]) {
    if (!values.length) {
      return null
    }

    return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
  }

  private opsProblemCutoff() {
    const hours = Number(process.env.ANALYSIS_OPS_PROBLEM_WINDOW_HOURS ?? '24')
    const safeHours = Number.isFinite(hours) && hours > 0 ? hours : 24
    return new Date(Date.now() - safeHours * 60 * 60 * 1000)
  }

  private getExtension(fileName: string) {
    const dotIndex = fileName.lastIndexOf('.')
    return dotIndex >= 0 ? fileName.slice(dotIndex).toLowerCase() : ''
  }

  private normalizeTargetRating(value?: string | null) {
    const normalized = (value ?? 'raw').trim()
    if (!normalized || normalized.toLowerCase() === 'raw') {
      return null
    }

    if (['6+', '12+', '16+', '18+'].includes(normalized)) {
      return normalized
    }

    throw new BadRequestException('Некорректная цель анализа. Используйте raw, 6+, 12+, 16+ или 18+.')
  }

  private privateFileLabel(id: string) {
    return `Файл #${id.replace(/-/g, '').slice(0, 8)}`
  }

  private privateUserLabel(id: string) {
    return `Пользователь #${id.replace(/-/g, '').slice(0, 8)}`
  }
}
