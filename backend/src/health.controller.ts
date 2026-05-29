import { Controller, Get } from '@nestjs/common'
import { ConfigService } from '@nestjs/config'
import axios from 'axios'
import IORedis from 'ioredis'
import { PrismaService } from './prisma/prisma.service'

@Controller('api/health')
export class HealthController {
  @Get()
  health() {
    return { status: 'ok' }
  }
}

@Controller('api/ready')
export class ReadyController {
  constructor(
    private readonly prisma: PrismaService,
    private readonly configService: ConfigService
  ) {}

  @Get()
  async ready() {
    const db = await this.checkDb()
    const redis = await this.checkRedis()
    const llm = await this.checkLlm()
    const ready = db.ready && redis.ready && llm.ready

    return {
      ready,
      db,
      redis,
      llm,
      version: this.configService.get<string>('APP_VERSION') ?? 'dev'
    }
  }

  private async checkDb() {
    try {
      await this.prisma.$queryRaw`SELECT 1`
      return { ready: true }
    } catch (error) {
      return { ready: false, error: error instanceof Error ? error.message : 'DB недоступна' }
    }
  }

  private async checkRedis() {
    const redisUrl = this.configService.get<string>('REDIS_URL') ?? 'redis://127.0.0.1:6379'
    const redis = new IORedis(redisUrl, { lazyConnect: true, maxRetriesPerRequest: 1 })
    try {
      await redis.connect()
      await redis.ping()
      return { ready: true }
    } catch (error) {
      return { ready: false, error: error instanceof Error ? error.message : 'Redis недоступен' }
    } finally {
      redis.disconnect()
    }
  }

  private async checkLlm() {
    const baseUrl = this.configService.get<string>('LLM_SERVICE_URL') ?? 'http://127.0.0.1:8001'
    try {
      const response = await axios.get(`${baseUrl}/api/analysis/health`, { timeout: 3000 })
      return {
        ready: response.status >= 200 && response.status < 300,
        detail: response.data
      }
    } catch (error) {
      return { ready: false, error: error instanceof Error ? error.message : 'LLM service недоступен' }
    }
  }
}
