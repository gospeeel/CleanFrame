import {
  BadGatewayException,
  BadRequestException,
  Injectable,
  ServiceUnavailableException
} from '@nestjs/common'
import { ConfigService } from '@nestjs/config'
import axios, { AxiosError } from 'axios'
import FormData = require('form-data')
import { readFile } from 'node:fs/promises'
import { normalizeUploadFileName } from './file-name'

@Injectable()
export class LlmService {
  private readonly llmServiceUrl: string
  private readonly timeoutMs: number

  constructor(private readonly configService: ConfigService) {
    this.llmServiceUrl =
      this.configService.get<string>('LLM_SERVICE_URL') ?? 'http://127.0.0.1:8001'
    this.timeoutMs = Number(this.configService.get<string>('LLM_ANALYSIS_TIMEOUT_MS') ?? 10 * 60 * 1000)
  }

  async send(file: Express.Multer.File) {
    return this.sendBuffer({
      buffer: file.buffer,
      fileName: normalizeUploadFileName(file.originalname),
      mimeType: file.mimetype
    })
  }

  async sendStoredFile(file: {
    fileName: string
    filePath: string | null
    mimeType: string
    analysisId?: string
    requestId?: string
    targetRating?: string | null
  }) {
    if (!file.filePath) {
      throw new BadRequestException('Исходный файл анализа недоступен')
    }

    const buffer = await readFile(file.filePath)
    return this.sendBuffer({
      buffer,
      fileName: file.fileName,
      mimeType: file.mimeType,
      analysisId: file.analysisId,
      requestId: file.requestId,
      targetRating: file.targetRating
    })
  }

  private async sendBuffer(file: {
    buffer: Buffer
    fileName: string
    mimeType: string
    analysisId?: string
    requestId?: string
    targetRating?: string | null
  }) {
    const form = new FormData()
    form.append('file', file.buffer, {
      filename: normalizeUploadFileName(file.fileName),
      contentType: file.mimeType
    })
    form.append('target_rating', file.targetRating ?? 'raw')

    try {
      const response = await axios.post(`${this.llmServiceUrl}/api/analysis/run`, form, {
        headers: {
          ...form.getHeaders(),
          ...(file.analysisId ? { 'x-analysis-id': file.analysisId } : {}),
          ...(file.requestId || file.analysisId ? { 'x-request-id': file.requestId ?? file.analysisId } : {})
        },
        maxBodyLength: Infinity,
        maxContentLength: Infinity,
        timeout: this.timeoutMs
      })

      return response.data
    } catch (error) {
      if (!axios.isAxiosError(error)) {
        throw new BadGatewayException('LLM сервис вернул неизвестную ошибку')
      }

      this.forwardLlmError(error)
    }
  }

  private forwardLlmError(error: AxiosError<{ detail?: string }>): never {
    const status = error.response?.status
    const detail = error.response?.data?.detail ?? 'LLM сервис недоступен'

    if (status === 400) {
      throw new BadRequestException(detail)
    }

    if (status === 503) {
      throw new ServiceUnavailableException(detail)
    }

    throw new BadGatewayException(detail)
  }
}
