import { Module } from '@nestjs/common'
import { AuthModule } from '../auth/auth.module'
import { LlmModule } from '../llm/llm.module'
import { NotificationsModule } from '../notifications/notifications.module'
import { AnalysisFileStorageService } from './analysis-file-storage.service'
import { AnalysisMonitorService } from './analysis-monitor.service'
import { AnalysisProcessorService } from './analysis-processor.service'
import { AnalysisQueueService } from './analysis-queue.service'
import { AnalysisRetentionService } from './analysis-retention.service'
import { AnalysesController } from './analyses.controller'
import { AnalysesService } from './analyses.service'

@Module({
  imports: [AuthModule, LlmModule, NotificationsModule],
  controllers: [AnalysesController],
  providers: [
    AnalysesService,
    AnalysisFileStorageService,
    AnalysisMonitorService,
    AnalysisProcessorService,
    AnalysisQueueService,
    AnalysisRetentionService
  ],
  exports: [AnalysisQueueService]
})
export class AnalysesModule {}
