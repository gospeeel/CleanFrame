import * as assert from 'node:assert/strict'
import { BadRequestException, ServiceUnavailableException } from '@nestjs/common'
import { AnalysisStatus, NotificationType } from '@prisma/client'
import { AnalysesService } from '../src/analyses/analyses.service'
import { AnalysisMonitorService } from '../src/analyses/analysis-monitor.service'
import { AnalysisProcessorService } from '../src/analyses/analysis-processor.service'
import { AnalysisRetentionService } from '../src/analyses/analysis-retention.service'

const now = new Date('2026-05-28T12:00:00.000Z')

async function testCreateEnqueuesQueuedAnalysis() {
  const calls: string[] = []
  const prisma = {
    analysis: {
      create: async ({ data }: any) => {
        calls.push(`create:${data.status}`)
        return analysisRecord({ id: 'analysis-1', userId: data.userId, status: data.status })
      },
      update: async ({ data }: any) => {
        calls.push(`update:${data.queueJobId}`)
        return analysisRecord({ id: 'analysis-1', userId: 'user-1', ...data })
      }
    }
  }
  const fileStorage = {
    save: async () => ({ fileName: 'script.docx', filePath: '/tmp/script.docx', mimeType: 'application/docx' })
  }
  const queue = {
    enqueue: async (data: any) => {
      assert.deepEqual(data, { analysisId: 'analysis-1', userId: 'user-1', requestId: 'request-1' })
      return 'job-1'
    }
  }

  const service = new AnalysesService(prisma as any, fileStorage as any, queue as any, {} as any, auditLog() as any)
  const result = await service.create('user-1', uploadFile(), 'request-1')

  assert.equal(result.id, 'analysis-1')
  assert.equal(result.status, AnalysisStatus.QUEUED)
  assert.deepEqual(calls, ['create:QUEUED', 'update:undefined', 'update:job-1'])
}

async function testRetryAndCancelRequireOwnedAnalysis() {
  const records = new Map<string, any>([
    ['owned-failed', analysisRecord({
      id: 'owned-failed',
      userId: 'user-1',
      status: AnalysisStatus.FAILED,
      sourceFilePath: '/tmp/owned/script.docx'
    })],
    ['owned-queued', analysisRecord({
      id: 'owned-queued',
      userId: 'user-1',
      status: AnalysisStatus.QUEUED,
      queueJobId: 'job-queued',
      sourceFilePath: '/tmp/queued/script.docx'
    })]
  ])
  const notifications: any[] = []
  const prisma = {
    analysis: {
      findFirst: async ({ where }: any) => {
        const record = records.get(where.id)
        return record?.userId === where.userId ? record : null
      },
      update: async ({ where, data }: any) => {
        const updated = { ...records.get(where.id), ...data }
        records.set(where.id, updated)
        return updated
      }
    }
  }
  const queue = {
    enqueue: async (data: any) => {
      assert.equal(data.requestId, 'request-retry')
      return 'job-retry'
    },
    remove: async (jobId: string) => {
      assert.equal(jobId, 'job-queued')
      return true
    }
  }
  const fileStorage = {
    remove: async (filePath: string) => {
      assert.equal(filePath, '/tmp/queued/script.docx')
    }
  }
  const notificationsService = {
    create: async (input: any) => notifications.push(input)
  }
  const service = new AnalysesService(prisma as any, fileStorage as any, queue as any, notificationsService as any, auditLog() as any)

  const retry = await service.retry('user-1', 'owned-failed', 'request-retry')
  assert.equal(retry.status, AnalysisStatus.QUEUED)
  assert.equal(records.get('owned-failed').queueJobId, 'job-retry')

  const cancelled = await service.cancel('user-1', 'owned-queued')
  assert.equal(cancelled.status, AnalysisStatus.CANCELLED)
  assert.equal(records.get('owned-queued').sourceFilePath, null)
  assert.equal(notifications[0].type, NotificationType.ANALYSIS_CANCELLED)

  await assert.rejects(() => service.retry('user-2', 'owned-failed'), /Анализ не найден/)
}

async function testRetryPolicySeparatesValidationAndTransientErrors() {
  const processor = new AnalysisProcessorService({} as any, {} as any, {} as any, {} as any, auditLog() as any)

  assert.equal(processor.isRetryableError(new BadRequestException('bad file')), false)
  assert.equal(processor.isRetryableError(new ServiceUnavailableException('llm unavailable')), true)
  assert.equal(processor.isRetryableError(new Error('network timeout')), true)
}

async function testLongRunningNotificationCreatedOnce() {
  const notifications: any[] = []
  const prisma = {
    analysis: {
      findMany: async () => [
        analysisRecord({
          id: 'slow-analysis',
          userId: 'user-1',
          status: AnalysisStatus.PROCESSING,
          queuedAt: new Date('2026-05-28T11:00:00.000Z')
        })
      ]
    }
  }
  const service = new AnalysisMonitorService(prisma as any, {
    create: async (input: any) => notifications.push(input)
  } as any)

  const result = await service.createLongRunningNotifications(now)

  assert.equal(result.created, 1)
  assert.equal(notifications[0].type, NotificationType.ANALYSIS_LONG_RUNNING)
  assert.equal(notifications[0].analysisId, 'slow-analysis')
}

async function testRetentionCleanupRemovesExpiredTerminalFiles() {
  const removed: string[] = []
  const updates: any[] = []
  const prisma = {
    analysis: {
      findMany: async () => [
        { id: 'failed-old', sourceFilePath: '/tmp/failed-old/script.docx' }
      ],
      update: async ({ where, data }: any) => updates.push({ where, data })
    }
  }
  const service = new AnalysisRetentionService(prisma as any, {
    remove: async (filePath: string) => removed.push(filePath)
  } as any, auditLog() as any)

  const result = await service.cleanupExpiredSourceFiles(now)

  assert.equal(result.removed, 1)
  assert.deepEqual(removed, ['/tmp/failed-old/script.docx'])
  assert.deepEqual(updates, [{ where: { id: 'failed-old' }, data: { sourceFilePath: null } }])
}

function auditLog() {
  return {
    record: async () => undefined
  }
}

async function testAdminOpsMasksPrivateFieldsInPrivacyMode() {
  const previousPrivacyMode = process.env.PRIVACY_MODE
  process.env.PRIVACY_MODE = 'true'
  try {
    const analysis = analysisRecord({
      id: '11111111-2222-3333-4444-555555555555',
      fileName: 'Аватар.txt',
      status: AnalysisStatus.FAILED,
      attempts: 1,
      user: {
        id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
        login: 'admin',
        email: 'admin@example.com'
      }
    })
    const prisma = {
      analysis: {
        count: async () => 1,
        groupBy: async () => [{ status: AnalysisStatus.FAILED, _count: { _all: 1 } }],
        findMany: async ({ include }: any) => include ? [analysis] : []
      }
    }
    const queue = {
      getStatus: async () => ({
        waiting: 0,
        active: 0,
        delayed: 0,
        failed: 0,
        completed: 0,
        concurrency: 1,
        utilizationPercent: 0
      })
    }
    const service = new AnalysesService(prisma as any, {} as any, queue as any, {} as any, auditLog() as any)

    const summary = await service.adminOpsSummary()

    assert.equal(summary.items[0].fileName, 'Файл #11111111')
    assert.equal(summary.items[0].userLogin, 'Пользователь #aaaaaaaa')
    assert.equal(summary.items[0].userEmail, '[filtered]')
  } finally {
    if (previousPrivacyMode === undefined) {
      delete process.env.PRIVACY_MODE
    } else {
      process.env.PRIVACY_MODE = previousPrivacyMode
    }
  }
}

async function main() {
  await testCreateEnqueuesQueuedAnalysis()
  await testRetryAndCancelRequireOwnedAnalysis()
  await testRetryPolicySeparatesValidationAndTransientErrors()
  await testLongRunningNotificationCreatedOnce()
  await testRetentionCleanupRemovesExpiredTerminalFiles()
  await testAdminOpsMasksPrivateFieldsInPrivacyMode()
  console.log('analysis workflow verification passed')
}

function uploadFile(): Express.Multer.File {
  return {
    originalname: 'script.docx',
    mimetype: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    buffer: Buffer.from('docx'),
    fieldname: 'file',
    encoding: '7bit',
    size: 4,
    destination: '',
    filename: '',
    path: '',
    stream: null as any
  }
}

function analysisRecord(overrides: Record<string, unknown> = {}) {
  return {
    id: 'analysis-id',
    userId: 'user-1',
    fileName: 'script.docx',
    status: AnalysisStatus.QUEUED,
    maxRating: null,
    riskCount: 0,
    reviewCount: 0,
    processingTime: null,
    resultJson: null,
    errorMessage: null,
    errorCode: null,
    sourceFilePath: null,
    queueJobId: null,
    queuedAt: now,
    startedAt: null,
    attempts: 0,
    workerId: null,
    completedAt: null,
    createdAt: now,
    updatedAt: now,
    ...overrides
  }
}

void main().catch((error) => {
  console.error(error)
  process.exit(1)
})
