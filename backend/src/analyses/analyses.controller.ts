import {
  BadRequestException,
  Controller,
  Get,
  Body,
  Param,
  Post,
  Req,
  Res,
  UploadedFile,
  UseGuards,
  UseInterceptors
} from '@nestjs/common'
import { FileInterceptor } from '@nestjs/platform-express'
import { UserRole } from '@prisma/client'
import { Request, Response } from 'express'
import { memoryStorage } from 'multer'
import { Roles } from '../auth/roles.decorator'
import { RolesGuard } from '../auth/roles.guard'
import { CurrentUser } from '../auth/current-user.decorator'
import { JwtAuthGuard } from '../auth/jwt-auth.guard'
import { JwtUser } from '../auth/auth.types'
import { AnalysisPdfService } from './analysis-pdf.service'
import { AnalysesService } from './analyses.service'

const SUPPORTED_EXTENSIONS = new Set(['.docx', '.pdf', '.txt'])

@Controller('api/analyses')
@UseGuards(JwtAuthGuard)
export class AnalysesController {
  constructor(
    private readonly analysesService: AnalysesService,
    private readonly pdfService: AnalysisPdfService
  ) {}

  @Post()
  @UseInterceptors(
    FileInterceptor('file', {
      storage: memoryStorage(),
      limits: {
        fileSize: 50 * 1024 * 1024
      }
    })
  )
  create(
    @CurrentUser() user: JwtUser,
    @UploadedFile() file: Express.Multer.File | undefined,
    @Body('targetRating') targetRating: string | undefined,
    @Req() request: Request
  ) {
    this.assertFile(file)
    return this.analysesService.create(user.sub, file, this.requestId(request), targetRating)
  }

  @Get()
  list(@CurrentUser() user: JwtUser) {
    return this.analysesService.list(user.sub)
  }

  @Get('admin/ops')
  @UseGuards(RolesGuard)
  @Roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)
  adminOps() {
    return this.analysesService.adminOpsSummary()
  }

  @Post('admin/ops/:id/retry')
  @UseGuards(RolesGuard)
  @Roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)
  adminRetry(@Param('id') id: string, @Req() request: Request) {
    return this.analysesService.retryAsAdmin(id, this.requestId(request))
  }

  @Get(':id/export/pdf')
  async exportPdf(@CurrentUser() user: JwtUser, @Param('id') id: string, @Res() response: Response) {
    const details = await this.analysesService.get(user.sub, id)
    const pdf = await this.pdfService.generate(details)

    response.setHeader('Content-Type', 'application/pdf')
    response.setHeader('Content-Length', String(pdf.buffer.length))
    response.setHeader('Content-Disposition', `attachment; filename="${this.asciiFileName(pdf.fileName)}"; filename*=UTF-8''${encodeURIComponent(pdf.fileName)}`)
    response.send(pdf.buffer)
  }

  @Get(':id')
  get(@CurrentUser() user: JwtUser, @Param('id') id: string) {
    return this.analysesService.get(user.sub, id)
  }

  @Post(':id/retry')
  retry(@CurrentUser() user: JwtUser, @Param('id') id: string, @Req() request: Request) {
    return this.analysesService.retry(user.sub, id, this.requestId(request))
  }

  @Post(':id/cancel')
  cancel(@CurrentUser() user: JwtUser, @Param('id') id: string) {
    return this.analysesService.cancel(user.sub, id)
  }

  private assertFile(file?: Express.Multer.File): asserts file is Express.Multer.File {
    if (!file) {
      throw new BadRequestException('Файл обязателен')
    }

    const extension = this.getExtension(file.originalname)
    if (!SUPPORTED_EXTENSIONS.has(extension)) {
      throw new BadRequestException('Поддерживаются только файлы .docx, .pdf и .txt')
    }

    if (!file.buffer?.length) {
      throw new BadRequestException('Загруженный файл пуст')
    }
  }

  private getExtension(fileName: string) {
    const dotIndex = fileName.lastIndexOf('.')
    return dotIndex >= 0 ? fileName.slice(dotIndex).toLowerCase() : ''
  }

  private requestId(request: Request) {
    const value = request.headers['x-request-id']
    return Array.isArray(value) ? value[0] : value
  }

  private asciiFileName(fileName: string) {
    return fileName.replace(/[^\x20-\x7E]/g, '_').replace(/["\\]/g, '_')
  }
}
