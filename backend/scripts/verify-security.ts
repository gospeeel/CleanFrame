import * as assert from 'node:assert/strict'
import { AnalysisStatus } from '@prisma/client'
import { AnalysisProcessorService } from '../src/analyses/analysis-processor.service'
import { scrubSentryEvent } from '../src/instrument'

async function testDoneRemovesSourceFileAndNullsPath() {
  const removed: Array<string | null | undefined> = []
  const updates: any[] = []
  const auditEvents: any[] = []
  const notifications: any[] = []
  const prisma = {
    analysis: {
      findUnique: async () => analysisRecord({
        id: 'analysis-done',
        sourceFilePath: '/tmp/analysis-done/script.txt'
      }),
      update: async ({ data }: any) => {
        updates.push(data)
        return analysisRecord({ id: 'analysis-done', ...data })
      }
    }
  }
  const llmService = {
    sendStoredFile: async () => ({
      result: {
        статистика: {
          максимальный_рейтинг: '0+',
          всего_подозрительных: 0,
          сцен_требующих_проверки: 0,
          время_обработки: 0.1
        },
        все_подозрительные_сцены: []
      }
    })
  }
  const processor = new AnalysisProcessorService(
    prisma as any,
    llmService as any,
    { remove: async (filePath: string | null | undefined) => removed.push(filePath) } as any,
    { create: async (input: any) => notifications.push(input) } as any,
    { record: async (input: any) => auditEvents.push(input) } as any
  )

  await processor.process('analysis-done', 'worker-1', 'job-1', 'request-1')

  assert.deepEqual(removed, ['/tmp/analysis-done/script.txt'])
  assert.equal(updates.some((item) => item.status === AnalysisStatus.DONE && item.sourceFilePath === null), true)
  assert.equal(notifications.length, 1)
  assert.equal(auditEvents.some((item) => item.action === 'analysis.done'), true)
  assert.equal(auditEvents.some((item) => item.action === 'analysis.source_file_removed'), true)
}

function testSentryScrubbingRemovesSensitivePayloads() {
  const previousPrivacyMode = process.env.PRIVACY_MODE
  process.env.PRIVACY_MODE = 'true'
  try {
    const event = scrubSentryEvent({
      request: {
        headers: {
          authorization: 'Bearer secret-token',
          cookie: 'session=secret',
          other: 'ok'
        },
        data: { scriptText: 'full script body' },
        cookies: { session: 'secret' }
      },
      contexts: {
        user: { email: 'user@example.com' },
        file: { fileName: 'secret-script.txt', safe: 'value' },
        auth: { accessToken: 'secret-token' }
      },
      extra: {
        nested: {
          password: 'secret',
          originalName: 'raw-file.txt',
          keep: 'ok'
        }
      }
    })

    assert.equal(event.request.headers.authorization, undefined)
    assert.equal(event.request.headers.cookie, undefined)
    assert.equal(event.request.data, undefined)
    assert.equal(event.request.cookies, undefined)
    assert.equal((event.contexts as any).user.email, '[Filtered]')
    assert.equal((event.contexts as any).file.fileName, '[Filtered]')
    assert.equal((event.contexts as any).auth.accessToken, '[Filtered]')
    assert.equal((event.extra as any).nested.password, '[Filtered]')
    assert.equal((event.extra as any).nested.originalName, '[Filtered]')
    assert.equal((event.extra as any).nested.keep, 'ok')
  } finally {
    if (previousPrivacyMode === undefined) {
      delete process.env.PRIVACY_MODE
    } else {
      process.env.PRIVACY_MODE = previousPrivacyMode
    }
  }
}

async function main() {
  await testDoneRemovesSourceFileAndNullsPath()
  testSentryScrubbingRemovesSensitivePayloads()
  console.log('security verification passed')
}

function analysisRecord(overrides: Record<string, unknown> = {}) {
  const now = new Date('2026-05-31T12:00:00.000Z')
  return {
    id: 'analysis-id',
    userId: 'user-1',
    fileName: 'script.txt',
    status: AnalysisStatus.QUEUED,
    maxRating: null,
    riskCount: 0,
    reviewCount: 0,
    processingTime: null,
    resultJson: null,
    errorMessage: null,
    errorCode: null,
    sourceFilePath: '/tmp/script.txt',
    queueJobId: 'job-1',
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
