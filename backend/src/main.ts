import './instrument'
import { NestFactory } from '@nestjs/core'
import { randomUUID } from 'node:crypto'
import { NextFunction, Request, Response } from 'express'
import { AppModule } from './app.module'

function getAllowedOrigins() {
  return new Set([
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:3001',
    'http://127.0.0.1:3001',
    ...((process.env.FRONTEND_URL ?? '')
      .split(',')
      .map((origin) => origin.trim())
      .filter(Boolean)),
    ...((process.env.CORS_ORIGINS ?? '')
      .split(',')
      .map((origin) => origin.trim())
      .filter(Boolean))
  ])
}

function isDevNetworkOrigin(origin: string) {
  try {
    const url = new URL(origin)
    const isDevPort = url.port === '3000' || url.port === '3001'
    const isLocalHost = url.hostname === 'localhost' || url.hostname === '127.0.0.1'
    const isPrivateIp =
      /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(url.hostname) ||
      /^192\.168\.\d{1,3}\.\d{1,3}$/.test(url.hostname) ||
      /^172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}$/.test(url.hostname)

    return url.protocol === 'http:' && isDevPort && (isLocalHost || isPrivateIp)
  } catch {
    return false
  }
}

async function bootstrap() {
  const app = await NestFactory.create(AppModule)
  const allowedOrigins = getAllowedOrigins()

  app.enableCors({
    origin: (origin: string | undefined, callback: (error: Error | null, allow?: boolean) => void) => {
      if (!origin || allowedOrigins.has(origin) || isDevNetworkOrigin(origin)) {
        callback(null, true)
        return
      }

      callback(new Error(`CORS origin is not allowed: ${origin}`))
    },
    credentials: true
  })

  app.use((request: Request, response: Response, next: NextFunction) => {
    const requestId = request.headers['x-request-id'] ?? randomUUID()
    request.headers['x-request-id'] = requestId
    response.setHeader('x-request-id', requestId)
    next()
  })

  const port = Number(process.env.PORT ?? 8000)
  await app.listen(port, '0.0.0.0')
}

void bootstrap()
