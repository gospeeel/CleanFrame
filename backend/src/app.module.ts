import { Module } from '@nestjs/common'
import { ConfigModule } from '@nestjs/config'
import { APP_FILTER } from '@nestjs/core'
import { SentryGlobalFilter, SentryModule } from '@sentry/nestjs/setup'
import { AnalysesModule } from './analyses/analyses.module'
import { AuthModule } from './auth/auth.module'
import { HealthController, ReadyController } from './health.controller'
import { LlmModule } from './llm/llm.module'
import { NotificationsModule } from './notifications/notifications.module'
import { PrismaModule } from './prisma/prisma.module'

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true
    }),
    SentryModule.forRoot(),
    PrismaModule,
    AuthModule,
    AnalysesModule,
    LlmModule,
    NotificationsModule
  ],
  controllers: [HealthController, ReadyController],
  providers: [
    {
      provide: APP_FILTER,
      useClass: SentryGlobalFilter
    }
  ]
})
export class AppModule {}
