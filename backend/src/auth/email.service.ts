import { Injectable } from '@nestjs/common'
import { ConfigService } from '@nestjs/config'
import nodemailer from 'nodemailer'

@Injectable()
export class EmailService {
  constructor(private readonly configService: ConfigService) {}

  async sendEmailChangeCode(to: string, code: string) {
    const host = this.configService.get<string>('SMTP_HOST')
    const port = Number(this.configService.get<string>('SMTP_PORT') ?? 587)
    const user = this.configService.get<string>('SMTP_USER')
    const pass = this.configService.get<string>('SMTP_PASSWORD')
    const from = this.configService.get<string>('SMTP_FROM') ?? user

    if (!host || !user || !pass || !from) {
      throw new Error('SMTP is not configured')
    }

    const transporter = nodemailer.createTransport({
      host,
      port,
      secure: port === 465,
      auth: { user, pass }
    })

    await transporter.sendMail({
      from,
      to,
      subject: 'Код подтверждения почты Чистый Кадр',
      text: `Ваш код подтверждения: ${code}. Он действует 10 минут.`,
      html: `<p>Ваш код подтверждения: <b>${code}</b></p><p>Он действует 10 минут.</p>`
    })
  }
}
