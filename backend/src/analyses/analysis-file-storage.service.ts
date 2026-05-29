import { Injectable } from '@nestjs/common'
import { mkdir, rm, writeFile } from 'node:fs/promises'
import { basename, dirname, join } from 'node:path'
import { normalizeUploadFileName } from '../llm/file-name'

@Injectable()
export class AnalysisFileStorageService {
  private readonly root = process.env.ANALYSIS_UPLOAD_DIR ?? join(process.cwd(), 'uploads', 'analysis')

  async save(analysisId: string, file: Express.Multer.File) {
    const dir = join(this.root, analysisId)
    await mkdir(dir, { recursive: true })

    const fileName = normalizeUploadFileName(file.originalname)
    const filePath = join(dir, fileName)
    await writeFile(filePath, file.buffer)

    return {
      fileName,
      filePath,
      mimeType: file.mimetype
    }
  }

  async remove(filePath: string | null | undefined) {
    if (!filePath) {
      return
    }

    await rm(dirname(filePath), { recursive: true, force: true })
  }

  safeName(filePath: string | null | undefined) {
    return filePath ? basename(filePath) : 'script'
  }
}
