import { Injectable, Logger } from '@nestjs/common'
import { Prisma } from '@prisma/client'
import { PrismaService } from '../prisma/prisma.service'

export const AUDIT_ACTIONS = {
  ANALYSIS_CREATED: 'analysis.created',
  ANALYSIS_CANCELLED: 'analysis.cancelled',
  ANALYSIS_DONE: 'analysis.done',
  ANALYSIS_FAILED: 'analysis.failed',
  ANALYSIS_DEAD_LETTER: 'analysis.dead_letter',
  SOURCE_FILE_REMOVED: 'analysis.source_file_removed'
} as const

@Injectable()
export class AuditLogService {
  private readonly logger = new Logger(AuditLogService.name)

  constructor(private readonly prisma: PrismaService) {}

  async record(input: {
    action: string
    userId?: string | null
    analysisId?: string | null
    metadata?: Prisma.InputJsonValue
  }) {
    try {
      await this.prisma.auditEvent.create({
        data: {
          action: input.action,
          userId: input.userId ?? null,
          analysisId: input.analysisId ?? null,
          metadata: input.metadata ?? Prisma.JsonNull
        }
      })
    } catch (error) {
      this.logger.warn(`Failed to write audit event ${input.action}: ${error instanceof Error ? error.message : String(error)}`)
    }
  }
}
