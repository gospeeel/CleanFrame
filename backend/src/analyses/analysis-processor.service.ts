import { Injectable, Logger } from '@nestjs/common'
import * as Sentry from '@sentry/nestjs'
import { AnalysisStatus, NotificationType, Prisma } from '@prisma/client'
import { LlmService } from '../llm/llm.service'
import { NotificationsService } from '../notifications/notifications.service'
import { PrismaService } from '../prisma/prisma.service'
import { AnalysisFileStorageService } from './analysis-file-storage.service'

@Injectable()
export class AnalysisProcessorService {
  private readonly logger = new Logger(AnalysisProcessorService.name)

  constructor(
    private readonly prisma: PrismaService,
    private readonly llmService: LlmService,
    private readonly fileStorage: AnalysisFileStorageService,
    private readonly notifications: NotificationsService
  ) {}

  async process(analysisId: string, workerId: string, queueJobId?: string, requestId?: string) {
    const analysis = await this.prisma.analysis.findUnique({ where: { id: analysisId } })
    if (!analysis || analysis.status === AnalysisStatus.CANCELLED) {
      return
    }

    Sentry.setTags({
      analysisId,
      queueJobId: queueJobId ?? analysis.queueJobId ?? undefined,
      workerId,
      requestId,
      status: AnalysisStatus.PROCESSING
    })
    Sentry.addBreadcrumb({
      category: 'analysis.worker',
      message: 'analysis status processing',
      level: 'info',
      data: { analysisId, queueJobId: queueJobId ?? analysis.queueJobId, workerId, requestId }
    })

    await this.prisma.analysis.update({
      where: { id: analysisId },
      data: {
        status: AnalysisStatus.PROCESSING,
        startedAt: analysis.startedAt ?? new Date(),
        attempts: { increment: 1 },
        workerId,
        errorMessage: null,
        errorCode: null
      }
    })

    try {
      const response = await this.llmService.sendStoredFile({
        fileName: analysis.fileName,
        filePath: analysis.sourceFilePath,
        mimeType: this.mimeTypeFromFileName(analysis.fileName),
        analysisId,
        requestId
      })
      const result = this.normalizeAnalysisResult(response?.result as Prisma.JsonValue)
      const stats = this.extractStats(result)

      await this.prisma.analysis.update({
        where: { id: analysisId },
        data: {
          status: AnalysisStatus.DONE,
          maxRating: stats.maxRating,
          riskCount: stats.riskCount,
          reviewCount: stats.reviewCount,
          processingTime: stats.processingTime,
          resultJson: result === null ? Prisma.JsonNull : result,
          completedAt: new Date()
        }
      })

      await this.fileStorage.remove(analysis.sourceFilePath)
      await this.notifications.create({
        userId: analysis.userId,
        type: NotificationType.ANALYSIS_DONE,
        analysisId,
        title: 'Анализ завершён',
        message: `${analysis.fileName}: отчёт готов к просмотру`
      })
      Sentry.addBreadcrumb({
        category: 'analysis.worker',
        message: 'analysis done',
        level: 'info',
        data: { analysisId, queueJobId: queueJobId ?? analysis.queueJobId, workerId, requestId }
      })
    } catch (error) {
      this.logger.error(`Analysis ${analysisId} failed`, error instanceof Error ? error.stack : undefined)
      throw error
    }
  }

  async markFailed(analysisId: string, error: unknown, context: FailureContext = {}) {
    return this.markTerminalFailure(analysisId, error, AnalysisStatus.FAILED, context)
  }

  async markDeadLetter(analysisId: string, error: unknown, context: FailureContext = {}) {
    return this.markTerminalFailure(analysisId, error, AnalysisStatus.DEAD_LETTER, context)
  }

  isRetryableError(error: unknown) {
    const status = this.httpStatus(error)
    if (status === 400 || status === 401 || status === 403 || status === 404 || status === 413 || status === 422) {
      return false
    }

    const code = this.errorCode(error)
    if (code === 'UNSUPPORTED_FILE_TYPE') {
      return false
    }

    return true
  }

  private async markTerminalFailure(
    analysisId: string,
    error: unknown,
    status: AnalysisStatus,
    context: FailureContext
  ) {
    const errorCode = status === AnalysisStatus.DEAD_LETTER ? 'DEAD_LETTER' : this.errorCode(error)
    const analysis = await this.prisma.analysis.update({
      where: { id: analysisId },
      data: {
        status,
        errorCode,
        errorMessage: error instanceof Error ? error.message : 'Не удалось выполнить анализ',
        completedAt: new Date()
      }
    })

    Sentry.withScope((scope) => {
      scope.setTags({
        analysisId,
        queueJobId: context.queueJobId ?? analysis.queueJobId ?? undefined,
        workerId: context.workerId ?? analysis.workerId ?? undefined,
        requestId: context.requestId,
        status,
        errorCode
      })
      scope.setContext('analysis_job', {
        analysisId,
        queueJobId: context.queueJobId ?? analysis.queueJobId,
        workerId: context.workerId ?? analysis.workerId,
        requestId: context.requestId,
        attemptsMade: context.attemptsMade,
        maxAttempts: context.maxAttempts
      })
      Sentry.addBreadcrumb({
        category: 'analysis.worker',
        message: status === AnalysisStatus.DEAD_LETTER ? 'analysis dead-letter' : 'analysis failed',
        level: 'error',
        data: {
          analysisId,
          queueJobId: context.queueJobId ?? analysis.queueJobId,
          workerId: context.workerId ?? analysis.workerId,
          requestId: context.requestId,
          attemptsMade: context.attemptsMade,
          maxAttempts: context.maxAttempts
        }
      })
      Sentry.captureException(error)
    })

    await this.notifications.create({
      userId: analysis.userId,
      type: NotificationType.ANALYSIS_FAILED,
      analysisId,
      title: status === AnalysisStatus.DEAD_LETTER ? 'Анализ отправлен в dead-letter' : 'Анализ завершился ошибкой',
      message: `${analysis.fileName}: ${analysis.errorMessage ?? 'не удалось выполнить анализ'}`
    })
  }

  private extractStats(result: Prisma.JsonValue) {
    const payload = this.asRecord(result)
    const stats = this.asRecord(payload?.['статистика'])
    const allScenes = this.asArray(payload?.['все_подозрительные_сцены'])
    const processedScenes = this.asArray(payload?.['обработанные_сцены'])
    const scenes = allScenes.length ? allScenes : processedScenes

    return {
      maxRating: this.asString(stats?.['максимальный_рейтинг']),
      riskCount:
        this.asNumber(stats?.['всего_подозрительных']) ??
        this.asNumber(stats?.['обработано_подозрительных']) ??
        scenes.length,
      reviewCount:
        this.asNumber(stats?.['сцен_требующих_проверки']) ??
        scenes.filter((scene) => this.asRecord(scene)?.needs_review === true).length,
      processingTime: this.asNumber(stats?.['время_обработки'])
    }
  }

  private normalizeAnalysisResult(result: Prisma.JsonValue): Prisma.JsonValue {
    const payload = this.asRecord(result)
    if (!payload) {
      return result
    }

    const normalizedPayload: Record<string, Prisma.JsonValue> = { ...payload }
    for (const key of ['все_подозрительные_сцены', 'обработанные_сцены', 'сцены_с_максимальным_рейтингом']) {
      const scenes = this.asArray(normalizedPayload[key])
      if (!scenes.length) {
        continue
      }

      normalizedPayload[key] = scenes.map((scene, index) => this.normalizeSceneTimeline(scene, index))
    }

    return normalizedPayload as Prisma.JsonValue
  }

  private normalizeSceneTimeline(scene: Prisma.JsonValue, index: number): Prisma.JsonValue {
    const record = this.asRecord(scene)
    if (!record) {
      return scene
    }

    const position = this.asNumber(record.timeline_position) ??
      this.asNumber(record.element_index) ??
      index + 1

    return {
      ...record,
      scene_id: record.scene_id ?? `scene-${index + 1}`,
      scene_header: record.scene_header ?? null,
      page: record.page ?? null,
      element_index: this.asNumber(record.element_index) ?? index + 1,
      timeline_position: position
    } as Prisma.JsonValue
  }

  private errorCode(error: unknown) {
    const response = this.httpStatus(error)

    if (response === 400) return 'UNSUPPORTED_FILE_TYPE'
    if (response === 503) return 'LLM_SERVICE_UNAVAILABLE'
    return 'ANALYSIS_FAILED'
  }

  private httpStatus(error: unknown) {
    return typeof error === 'object' && error !== null && 'getStatus' in error
      ? (error as { getStatus: () => number }).getStatus()
      : null
  }

  private mimeTypeFromFileName(fileName: string) {
    if (fileName.endsWith('.pdf')) return 'application/pdf'
    if (fileName.endsWith('.txt')) return 'text/plain'
    return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  }

  private asRecord(value: Prisma.JsonValue | undefined): Record<string, Prisma.JsonValue> | null {
    return value && typeof value === 'object' && !Array.isArray(value)
      ? value as Record<string, Prisma.JsonValue>
      : null
  }

  private asArray(value: Prisma.JsonValue | undefined): Prisma.JsonArray {
    return Array.isArray(value) ? value : []
  }

  private asString(value: Prisma.JsonValue | undefined): string | null {
    return typeof value === 'string' ? value : null
  }

  private asNumber(value: Prisma.JsonValue | undefined): number | null {
    return typeof value === 'number' && Number.isFinite(value) ? value : null
  }
}

interface FailureContext {
  queueJobId?: string | null
  workerId?: string | null
  requestId?: string | null
  attemptsMade?: number
  maxAttempts?: number
}
