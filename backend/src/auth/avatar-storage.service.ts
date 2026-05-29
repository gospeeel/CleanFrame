import { DeleteObjectCommand, PutObjectCommand, S3Client } from '@aws-sdk/client-s3'
import { BadRequestException, Injectable } from '@nestjs/common'
import { ConfigService } from '@nestjs/config'
import { randomBytes } from 'node:crypto'
import { extname } from 'node:path'

@Injectable()
export class AvatarStorageService {
  private readonly client: S3Client

  constructor(private readonly configService: ConfigService) {
    this.client = new S3Client({
      endpoint: this.configService.get<string>('S3_ENDPOINT'),
      region: this.configService.get<string>('S3_REGION') ?? 'us-east-1',
      forcePathStyle: true,
      credentials: {
        accessKeyId: this.configService.get<string>('S3_ACCESS_KEY_ID') ?? '',
        secretAccessKey: this.configService.get<string>('S3_SECRET_ACCESS_KEY') ?? ''
      }
    })
  }

  async uploadAvatar(userId: string, file: Express.Multer.File) {
    const bucket = this.getBucket()
    const publicBaseUrl = this.configService.get<string>('S3_PUBLIC_BASE_URL')
    if (!publicBaseUrl) {
      throw new BadRequestException('S3_PUBLIC_BASE_URL не настроен')
    }

    if (!file.mimetype.startsWith('image/')) {
      throw new BadRequestException('Загрузите изображение')
    }

    if (file.size > 2 * 1024 * 1024) {
      throw new BadRequestException('Размер фото должен быть до 2 МБ')
    }

    const extension = extname(file.originalname) || '.jpg'
    const key = `avatars/${userId}/${randomBytes(12).toString('hex')}${extension}`

    await this.client.send(new PutObjectCommand({
      Bucket: bucket,
      Key: key,
      Body: file.buffer,
      ContentType: file.mimetype
    }))

    return `${publicBaseUrl.replace(/\/$/, '')}/${key}`
  }

  async deleteByUrl(url?: string | null) {
    if (!url) {
      return
    }

    const publicBaseUrl = this.configService.get<string>('S3_PUBLIC_BASE_URL')
    if (!publicBaseUrl || !url.startsWith(publicBaseUrl)) {
      return
    }

    const key = url.slice(publicBaseUrl.replace(/\/$/, '').length + 1)
    if (!key) {
      return
    }

    await this.client.send(new DeleteObjectCommand({
      Bucket: this.getBucket(),
      Key: key
    })).catch(() => undefined)
  }

  private getBucket() {
    const bucket = this.configService.get<string>('S3_BUCKET')
    if (!bucket) {
      throw new BadRequestException('S3_BUCKET не настроен')
    }

    return bucket
  }
}
