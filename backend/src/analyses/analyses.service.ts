import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common'
import { AnalysisStatus, NotificationType } from '@prisma/client'
import { NotificationsService } from '../notifications/notifications.service'
import { PrismaService } from '../prisma/prisma.service'
import { AnalysisFileStorageService } from './analysis-file-storage.service'
import { AnalysisQueueService } from './analysis-queue.service'
import { AnalysisDetails, AnalysisJobResponse, AnalysisListItem, AnalysisRecord } from './analyses.types'

@Injectable()
export class AnalysesService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly fileStorage: AnalysisFileStorageService,
    private readonly queue: AnalysisQueueService,
    private readonly notifications: NotificationsService
  ) {}

  async create(userId: string, file: Express.Multer.File, requestId?: string): Promise<AnalysisJobResponse> {
    const analysis = await this.prisma.analysis.create({
      data: {
        userId,
        fileName: file.originalname,
        status: AnalysisStatus.QUEUED
      }
    })

    const savedFile = await this.fileStorage.save(analysis.id, file)
    const queueJobId = await this.queue.enqueue({ analysisId: analysis.id, userId, requestId })

    await this.prisma.analysis.update({
      where: { id: analysis.id },
      data: {
        fileName: savedFile.fileName,
        sourceFilePath: savedFile.filePath,
        queueJobId
      }
    })

    return {
      id: analysis.id,
      status: analysis.status
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
      status: updated.status
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
        completedAt: new Date()
      }
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
}
