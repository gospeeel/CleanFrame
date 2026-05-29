import { Controller, Get, Param, Patch, Query, Res, UseGuards } from '@nestjs/common'
import { Response } from 'express'
import { CurrentUser } from '../auth/current-user.decorator'
import { JwtUser } from '../auth/auth.types'
import { JwtAuthGuard } from '../auth/jwt-auth.guard'
import { NotificationsService } from './notifications.service'

@Controller('api/notifications')
@UseGuards(JwtAuthGuard)
export class NotificationsController {
  constructor(private readonly notificationsService: NotificationsService) {}

  @Get()
  list(@CurrentUser() user: JwtUser, @Query('unreadOnly') unreadOnly?: string) {
    return this.notificationsService.list(user.sub, unreadOnly === 'true')
  }

  @Get('stream')
  async stream(@CurrentUser() user: JwtUser, @Res() response: Response) {
    response.setHeader('Content-Type', 'text/event-stream')
    response.setHeader('Cache-Control', 'no-cache, no-transform')
    response.setHeader('Connection', 'keep-alive')
    response.flushHeaders?.()

    const writeEvent = (event: string, data: unknown) => {
      response.write(`event: ${event}\n`)
      response.write(`data: ${JSON.stringify(data)}\n\n`)
    }

    writeEvent('ready', { ok: true })

    const subscriber = this.notificationsService.createSubscriber()
    const channel = this.notificationsService.channelForUser(user.sub)
    const heartbeat = setInterval(() => {
      writeEvent('heartbeat', { ts: Date.now() })
    }, 25_000)

    try {
      await subscriber.connect()
      await subscriber.subscribe(channel)
      subscriber.on('message', (_channel, message) => {
        response.write(`event: notification\n`)
        response.write(`data: ${message}\n\n`)
      })
    } catch (error) {
      writeEvent('error', {
        message: error instanceof Error ? error.message : 'Notification stream unavailable'
      })
      response.end()
      clearInterval(heartbeat)
      subscriber.disconnect()
      return
    }

    response.on('close', () => {
      clearInterval(heartbeat)
      void subscriber.unsubscribe(channel).finally(() => subscriber.disconnect())
    })
  }

  @Patch(':id/read')
  markRead(@CurrentUser() user: JwtUser, @Param('id') id: string) {
    return this.notificationsService.markRead(user.sub, id)
  }

  @Patch('read-all')
  markAllRead(@CurrentUser() user: JwtUser) {
    return this.notificationsService.markAllRead(user.sub)
  }
}
