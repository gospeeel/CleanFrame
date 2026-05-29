import { Injectable, Logger, OnApplicationShutdown, OnModuleInit } from '@nestjs/common'
import { ConfigService } from '@nestjs/config'
import * as Sentry from '@sentry/nestjs'
import { Queue, Worker, Job, UnrecoverableError, type ConnectionOptions } from 'bullmq'
import IORedis from 'ioredis'
import { breadcrumbQueueMetric, countQueueMetric, gaugeQueueMetric } from '../observability/queue-metrics'
import { AnalysisProcessorService } from './analysis-processor.service'

interface AnalysisJobData {
  analysisId: string
  userId: string
  requestId?: string
}

@Injectable()
export class AnalysisQueueService implements OnModuleInit, OnApplicationShutdown {
  private readonly logger = new Logger(AnalysisQueueService.name)
  private queue: Queue<AnalysisJobData> | null = null
  private worker: Worker<AnalysisJobData> | null = null
  private connectionOptions: ConnectionOptions | null = null
  private readonly queueName = 'analysis'
  private readonly workerId = `${process.pid}-${Date.now()}`
  private workerConcurrency = 1

  constructor(
    private readonly configService: ConfigService,
    private readonly processor: AnalysisProcessorService
  ) {}

  onModuleInit() {
    const redisUrl = this.configService.get<string>('REDIS_URL') ?? 'redis://127.0.0.1:6379'
    this.connectionOptions = this.buildConnectionOptions(redisUrl)
    this.queue = new Queue<AnalysisJobData>(this.queueName, { connection: this.connectionOptions })

    if (this.configService.get<string>('ANALYSIS_WORKER_ENABLED') === 'false') {
      return
    }

    const concurrency = Number(this.configService.get<string>('ANALYSIS_QUEUE_CONCURRENCY') ?? '1')
    const attempts = Number(this.configService.get<string>('ANALYSIS_QUEUE_ATTEMPTS') ?? '2')
    this.workerConcurrency = Number.isFinite(concurrency) && concurrency > 0 ? concurrency : 1

    this.worker = new Worker<AnalysisJobData>(
      this.queueName,
      async (job) => {
        countQueueMetric('queue.started', 1, {
          queue: this.queueName,
          workerId: this.workerId
        })
        await this.recordWorkerUtilization('processing_start')
        Sentry.addBreadcrumb({
          category: 'analysis.queue',
          message: 'analysis processing',
          level: 'info',
          data: {
            analysisId: job.data.analysisId,
            queueJobId: job.id,
            workerId: this.workerId,
            requestId: job.data.requestId,
            attemptsMade: job.attemptsMade
          }
        })

        try {
          await this.processor.process(job.data.analysisId, this.workerId, job.id, job.data.requestId)
        } catch (error) {
          if (!this.processor.isRetryableError(error)) {
            await this.processor.markFailed(job.data.analysisId, error, {
              queueJobId: job.id,
              workerId: this.workerId,
              requestId: job.data.requestId,
              attemptsMade: job.attemptsMade + 1,
              maxAttempts: Number(job.opts.attempts ?? attempts)
            })
            throw new UnrecoverableError(error instanceof Error ? error.message : 'Unrecoverable analysis error')
          }

          throw error
        }
      },
      {
        connection: this.connectionOptions,
        concurrency,
        limiter: {
          max: concurrency,
          duration: 1000
        }
      }
    )

    this.worker.on('failed', (job, error) => {
      if (!job) {
        return
      }

      const maxAttempts = Number(job.opts.attempts ?? attempts)
      this.logger.warn(
        `Analysis job ${job.id ?? 'unknown'} failed attempt ${job.attemptsMade}/${maxAttempts}: ${error.message}`
      )

      if (job.attemptsMade < maxAttempts) {
        Sentry.addBreadcrumb({
          category: 'analysis.queue',
          message: 'analysis retry scheduled',
          level: 'warning',
          data: {
            analysisId: job.data.analysisId,
            queueJobId: job.id,
            workerId: this.workerId,
            requestId: job.data.requestId,
            attemptsMade: job.attemptsMade,
            maxAttempts
          }
        })
        countQueueMetric('queue.retry_scheduled', 1, {
          queue: this.queueName,
          workerId: this.workerId
        })
        return
      }

      void this.processor.markDeadLetter(job.data.analysisId, error, {
        queueJobId: job.id,
        workerId: this.workerId,
        requestId: job.data.requestId,
        attemptsMade: job.attemptsMade,
        maxAttempts
      })
    })

    this.worker.on('completed', () => {
      void this.recordWorkerUtilization('completed')
    })
  }

  async enqueue(data: AnalysisJobData) {
    if (!this.queue) {
      throw new Error('Analysis queue is not initialized')
    }

    const attempts = Number(this.configService.get<string>('ANALYSIS_QUEUE_ATTEMPTS') ?? '2')
    const job = await this.queue.add('run-analysis', data, {
      attempts,
      backoff: {
        type: 'exponential',
        delay: 5000
      },
      removeOnComplete: {
        age: 24 * 60 * 60,
        count: 1000
      },
      removeOnFail: false
    })

    Sentry.addBreadcrumb({
      category: 'analysis.queue',
      message: 'analysis queued',
      level: 'info',
      data: {
        analysisId: data.analysisId,
        queueJobId: job.id,
        requestId: data.requestId
      }
    })
    countQueueMetric('queue.enqueued', 1, {
      queue: this.queueName
    })
    await this.recordWorkerUtilization('enqueued')

    return job.id ?? null
  }

  async remove(jobId: string | null | undefined) {
    if (!jobId || !this.queue) {
      return false
    }

    const job = await Job.fromId(this.queue, jobId)
    if (!job) {
      return false
    }

    await job.remove()
    return true
  }

  async ping() {
    const redisUrl = this.configService.get<string>('REDIS_URL') ?? 'redis://127.0.0.1:6379'
    const redis = new IORedis(redisUrl, { lazyConnect: true, maxRetriesPerRequest: 1 })
    try {
      await redis.connect()
      return await redis.ping()
    } finally {
      redis.disconnect()
    }
  }

  async getStatus() {
    if (!this.queue) {
      return {
        active: 0,
        waiting: 0,
        delayed: 0,
        failed: 0,
        completed: 0,
        concurrency: this.workerConcurrency,
        utilizationPercent: 0
      }
    }

    const counts = await this.queue.getJobCounts('active', 'waiting', 'delayed', 'failed', 'completed')
    const active = counts.active ?? 0
    return {
      active,
      waiting: counts.waiting ?? 0,
      delayed: counts.delayed ?? 0,
      failed: counts.failed ?? 0,
      completed: counts.completed ?? 0,
      concurrency: this.workerConcurrency,
      utilizationPercent: Math.min(100, (active / this.workerConcurrency) * 100)
    }
  }

  async onApplicationShutdown() {
    await this.worker?.close()
    await this.queue?.close()
  }

  private async recordWorkerUtilization(stage: string) {
    if (!this.queue) {
      return
    }

    try {
      const counts = await this.queue.getJobCounts('active', 'waiting', 'delayed', 'failed')
      const active = counts.active ?? 0
      const waiting = (counts.waiting ?? 0) + (counts.delayed ?? 0)
      const utilizationPercent = Math.min(100, (active / this.workerConcurrency) * 100)

      gaugeQueueMetric('worker.active_jobs', active, 'none', {
        queue: this.queueName,
        workerId: this.workerId,
        stage
      })
      gaugeQueueMetric('worker.waiting_jobs', waiting, 'none', {
        queue: this.queueName,
        workerId: this.workerId,
        stage
      })
      gaugeQueueMetric('worker.concurrency_utilization', utilizationPercent, 'percent', {
        queue: this.queueName,
        workerId: this.workerId,
        stage
      })
      breadcrumbQueueMetric('worker utilization sampled', {
        queue: this.queueName,
        workerId: this.workerId,
        stage,
        active,
        waiting,
        failed: counts.failed ?? 0,
        concurrency: this.workerConcurrency,
        utilizationPercent
      })
    } catch (error) {
      this.logger.warn(`Failed to collect queue metrics: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  private buildConnectionOptions(redisUrl: string): ConnectionOptions {
    const url = new URL(redisUrl)
    return {
      host: url.hostname,
      port: Number(url.port || 6379),
      username: url.username || undefined,
      password: url.password || undefined,
      maxRetriesPerRequest: null
    }
  }
}
