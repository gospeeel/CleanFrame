import {
  BadRequestException,
  Controller,
  Get,
  Param,
  Post,
  Req,
  UploadedFile,
  UseGuards,
  UseInterceptors
} from '@nestjs/common'
import { FileInterceptor } from '@nestjs/platform-express'
import { Request } from 'express'
import { memoryStorage } from 'multer'
import { CurrentUser } from '../auth/current-user.decorator'
import { JwtAuthGuard } from '../auth/jwt-auth.guard'
import { JwtUser } from '../auth/auth.types'
import { AnalysesService } from './analyses.service'

const SUPPORTED_EXTENSIONS = new Set(['.docx', '.pdf', '.txt'])

@Controller('api/analyses')
@UseGuards(JwtAuthGuard)
export class AnalysesController {
  constructor(private readonly analysesService: AnalysesService) {}

  @Post()
  @UseInterceptors(
    FileInterceptor('file', {
      storage: memoryStorage(),
      limits: {
        fileSize: 50 * 1024 * 1024
      }
    })
  )
  create(@CurrentUser() user: JwtUser, @UploadedFile() file: Express.Multer.File | undefined, @Req() request: Request) {
    this.assertFile(file)
    return this.analysesService.create(user.sub, file, this.requestId(request))
  }

  @Get()
  list(@CurrentUser() user: JwtUser) {
    return this.analysesService.list(user.sub)
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
}
