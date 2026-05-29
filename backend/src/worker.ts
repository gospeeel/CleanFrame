import './instrument'
import { Logger } from '@nestjs/common'
import { NestFactory } from '@nestjs/core'
import { AppModule } from './app.module'

async function bootstrap() {
  process.env.ANALYSIS_WORKER_ENABLED = process.env.ANALYSIS_WORKER_ENABLED ?? 'true'

  const logger = new Logger('AnalysisWorker')
  const app = await NestFactory.createApplicationContext(AppModule, {
    logger: ['log', 'error', 'warn', 'debug', 'verbose']
  })

  logger.log('Analysis worker started')

  const shutdown = async (signal: string) => {
    logger.log(`Analysis worker received ${signal}, shutting down`)
    await app.close()
    process.exit(0)
  }

  process.on('SIGTERM', () => void shutdown('SIGTERM'))
  process.on('SIGINT', () => void shutdown('SIGINT'))
}

void bootstrap()
