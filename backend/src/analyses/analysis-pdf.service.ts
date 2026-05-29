import { Injectable, InternalServerErrorException } from '@nestjs/common'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import PDFDocument = require('pdfkit')
import { AnalysisDetails } from './analyses.types'

type JsonRecord = Record<string, unknown>

interface PdfExport {
  buffer: Buffer
  fileName: string
}

const COLORS = {
  ink: '#17272d',
  muted: '#63757d',
  steel: '#526f7a',
  signal: '#b85836',
  brass: '#c49a58',
  milk: '#fbf8ef',
  line: '#d9ded9',
  white: '#ffffff'
}

@Injectable()
export class AnalysisPdfService {
  async generate(details: AnalysisDetails): Promise<PdfExport> {
    const fonts = this.resolveFonts()
    const doc = new PDFDocument({
      size: 'A4',
      margin: 42,
      bufferPages: true,
      info: {
        Title: `Clean Frame report: ${details.fileName}`,
        Author: 'Clean Frame'
      }
    })

    const chunks: Buffer[] = []
    const completed = new Promise<Buffer>((resolve, reject) => {
      doc.on('data', (chunk: Buffer) => chunks.push(Buffer.from(chunk)))
      doc.on('end', () => resolve(Buffer.concat(chunks)))
      doc.on('error', reject)
    })

    doc.registerFont('CleanSans', fonts.regular)
    doc.registerFont('CleanSansBold', fonts.bold)

    this.drawReport(doc, details)
    doc.end()

    return {
      buffer: await completed,
      fileName: this.exportFileName(details)
    }
  }

  private drawReport(doc: PDFKit.PDFDocument, details: AnalysisDetails) {
    const result = this.asRecord(details.result)
    const stats = this.asRecord(result?.статистика)
    const scenes = this.sceneList(result)

    this.cover(doc, details, stats, scenes.length)
    this.summary(doc, details, stats, scenes)
    this.sceneDetails(doc, scenes)
    this.footer(doc)
  }

  private cover(doc: PDFKit.PDFDocument, details: AnalysisDetails, stats: JsonRecord | null, sceneCount: number) {
    doc.rect(0, 0, doc.page.width, doc.page.height).fill(COLORS.milk)
    doc.rect(0, 0, doc.page.width, 92).fill(COLORS.ink)

    doc
      .fillColor(COLORS.white)
      .font('CleanSansBold')
      .fontSize(22)
      .text('Clean Frame', 42, 30)
      .font('CleanSans')
      .fontSize(10)
      .fillColor('#dce7e4')
      .text('Отчёт анализа сценария', 42, 59)

    doc
      .roundedRect(394, 28, 158, 38, 6)
      .fill(COLORS.signal)
      .fillColor(COLORS.white)
      .font('CleanSansBold')
      .fontSize(16)
      .text(this.maxRating(details, stats), 394, 38, { width: 158, align: 'center' })

    doc
      .fillColor(COLORS.ink)
      .font('CleanSansBold')
      .fontSize(26)
      .text('PDF-отчёт', 42, 132)
      .font('CleanSans')
      .fontSize(11)
      .fillColor(COLORS.muted)
      .text('Сформирован сервером Clean Frame. Подходит для отправки, хранения и проверки без открытия отдельной print-страницы.', 42, 168, {
        width: 500,
        lineGap: 3
      })

    this.metricCard(doc, 42, 222, 'Файл', details.fileName)
    this.metricCard(doc, 222, 222, 'Статус', this.statusLabel(details.status))
    this.metricCard(doc, 402, 222, 'Риск-сцен', String(sceneCount))
    this.metricCard(doc, 42, 310, 'Макс. рейтинг', this.maxRating(details, stats))
    this.metricCard(doc, 222, 310, 'Требуют проверки', String(details.reviewCount))
    this.metricCard(doc, 402, 310, 'Дата', this.dateLabel(details.createdAt))

    if (details.processingTime !== null) {
      this.metricCard(doc, 42, 398, 'Время обработки', `${Math.round(details.processingTime / 1000)} сек.`)
    }

    doc
      .moveTo(42, 526)
      .lineTo(552, 526)
      .lineWidth(1)
      .strokeColor(COLORS.line)
      .stroke()
      .fillColor(COLORS.muted)
      .font('CleanSans')
      .fontSize(9)
      .text(`ID анализа: ${details.id}`, 42, 544)
      .text(`Обновлён: ${this.dateTimeLabel(details.updatedAt)}`, 42, 562)
  }

  private summary(doc: PDFKit.PDFDocument, details: AnalysisDetails, stats: JsonRecord | null, scenes: JsonRecord[]) {
    doc.addPage()
    this.pageHeading(doc, 'Сводка')

    const total = this.value(stats, 'всего_элементов') ?? 'нет данных'
    const suspicious = this.value(stats, 'всего_подозрительных') ?? details.riskCount
    const processed = this.value(stats, 'обработано_подозрительных') ?? scenes.length

    this.infoRow(doc, 'Файл', details.fileName)
    this.infoRow(doc, 'Максимальный рейтинг', this.maxRating(details, stats))
    this.infoRow(doc, 'Всего элементов', String(total))
    this.infoRow(doc, 'Подозрительных элементов', String(suspicious))
    this.infoRow(doc, 'Обработано подозрительных', String(processed))
    this.infoRow(doc, 'Требуют проверки', String(details.reviewCount))

    const groups = this.groupScenes(scenes)
    let y = doc.y + 22
    doc.fillColor(COLORS.ink).font('CleanSansBold').fontSize(15).text('Категории риска', 42, y)
    y += 26

    if (!groups.length) {
      doc.fillColor(COLORS.muted).font('CleanSans').fontSize(10).text('Риск-сцены не найдены.', 42, y)
      return
    }

    for (const group of groups) {
      this.ensureSpace(doc, 58)
      y = doc.y
      doc
        .roundedRect(42, y, 510, 43, 5)
        .fillAndStroke(COLORS.white, COLORS.line)
        .fillColor(COLORS.ink)
        .font('CleanSansBold')
        .fontSize(11)
        .text(group.category, 56, y + 10, { width: 260 })
        .fillColor(COLORS.signal)
        .text(group.rating, 404, y + 10, { width: 48, align: 'right' })
        .fillColor(COLORS.muted)
        .font('CleanSans')
        .fontSize(9)
        .text(`${group.count} сцен`, 468, y + 12, { width: 70, align: 'right' })
      doc.y = y + 55
    }
  }

  private sceneDetails(doc: PDFKit.PDFDocument, scenes: JsonRecord[]) {
    doc.addPage()
    this.pageHeading(doc, 'Сцены и рекомендации')

    if (!scenes.length) {
      doc.fillColor(COLORS.muted).font('CleanSans').fontSize(10).text('Подозрительные сцены отсутствуют.')
      return
    }

    scenes.forEach((scene, index) => {
      this.ensureSpace(doc, 170)
      const y = doc.y
      const category = this.sceneCategory(scene)
      const rating = this.stringValue(scene.рейтинг) || this.stringValue(scene.rating) || 'нет данных'
      const text = this.stringValue(scene.текст_сцены) || this.stringValue(scene.text) || ''
      const recommendation = this.recommendationText(scene)

      doc
        .roundedRect(42, y, 510, 28, 5)
        .fill(COLORS.ink)
        .fillColor(COLORS.white)
        .font('CleanSansBold')
        .fontSize(10)
        .text(`#${index + 1}  ${category}`, 56, y + 8, { width: 340 })
        .text(rating, 472, y + 8, { width: 60, align: 'right' })

      doc
        .fillColor(COLORS.ink)
        .font('CleanSans')
        .fontSize(10)
        .text(this.truncate(text, 900), 56, y + 44, { width: 476, lineGap: 3 })

      if (this.needsReview(scene)) {
        doc
          .fillColor(COLORS.signal)
          .font('CleanSansBold')
          .fontSize(9)
          .text('Требует проверки', 56, doc.y + 8)
      }

      if (recommendation) {
        doc
          .fillColor(COLORS.steel)
          .font('CleanSansBold')
          .fontSize(9)
          .text('Рекомендация', 56, doc.y + 10)
          .fillColor(COLORS.muted)
          .font('CleanSans')
          .fontSize(9)
          .text(this.truncate(recommendation, 700), 56, doc.y + 4, { width: 476, lineGap: 2 })
      }

      const evidence = this.evidenceText(scene)
      if (evidence) {
        doc
          .fillColor(COLORS.brass)
          .font('CleanSansBold')
          .fontSize(9)
          .text('Основание', 56, doc.y + 8)
          .fillColor(COLORS.muted)
          .font('CleanSans')
          .fontSize(9)
          .text(this.truncate(evidence, 420), 56, doc.y + 4, { width: 476, lineGap: 2 })
      }

      doc.moveDown(1.3)
    })
  }

  private footer(doc: PDFKit.PDFDocument) {
    const range = doc.bufferedPageRange()

    for (let i = range.start; i < range.start + range.count; i += 1) {
      doc.switchToPage(i)
      doc
        .moveTo(42, 794)
        .lineTo(552, 794)
        .lineWidth(1)
        .strokeColor(COLORS.line)
        .stroke()
        .fillColor(COLORS.muted)
        .font('CleanSans')
        .fontSize(8)
        .text('Clean Frame', 42, 806)
        .text(`${i + 1} / ${range.count}`, 500, 806, { width: 52, align: 'right' })
    }
  }

  private pageHeading(doc: PDFKit.PDFDocument, title: string) {
    doc.rect(0, 0, doc.page.width, 74).fill(COLORS.milk)
    doc.fillColor(COLORS.ink).font('CleanSansBold').fontSize(20).text(title, 42, 34)
    doc.moveTo(42, 78).lineTo(552, 78).lineWidth(1).strokeColor(COLORS.line).stroke()
    doc.y = 104
  }

  private metricCard(doc: PDFKit.PDFDocument, x: number, y: number, label: string, value: string) {
    doc
      .roundedRect(x, y, 150, 58, 6)
      .fillAndStroke(COLORS.white, COLORS.line)
      .fillColor(COLORS.muted)
      .font('CleanSansBold')
      .fontSize(8)
      .text(label.toUpperCase(), x + 12, y + 11, { width: 126 })
      .fillColor(COLORS.ink)
      .fontSize(11)
      .text(this.truncate(value, 54), x + 12, y + 29, { width: 126, height: 22 })
  }

  private infoRow(doc: PDFKit.PDFDocument, label: string, value: string) {
    const y = doc.y
    doc
      .fillColor(COLORS.muted)
      .font('CleanSansBold')
      .fontSize(9)
      .text(label, 42, y, { width: 170 })
      .fillColor(COLORS.ink)
      .font('CleanSans')
      .text(value, 220, y, { width: 330 })
    doc.y = y + 22
  }

  private ensureSpace(doc: PDFKit.PDFDocument, height: number) {
    if (doc.y + height > 780) {
      doc.addPage()
      doc.y = 42
    }
  }

  private sceneList(result: JsonRecord | null) {
    const raw =
      this.asArray(result?.все_подозрительные_сцены) ??
      this.asArray(result?.обработанные_сцены) ??
      this.asArray(result?.сцены_с_максимальным_рейтингом) ??
      []

    return raw.map((item) => this.asRecord(item)).filter((item): item is JsonRecord => item !== null)
  }

  private groupScenes(scenes: JsonRecord[]) {
    const groups = new Map<string, { category: string; count: number; rating: string }>()

    for (const scene of scenes) {
      const category = this.sceneCategory(scene)
      const rating = this.stringValue(scene.рейтинг) || this.stringValue(scene.rating) || '0+'
      const current = groups.get(category)

      if (!current) {
        groups.set(category, { category, count: 1, rating })
        continue
      }

      current.count += 1
      current.rating = this.higherRating(current.rating, rating)
    }

    return [...groups.values()].sort((left, right) => right.count - left.count)
  }

  private sceneCategory(scene: JsonRecord) {
    return (
      this.stringValue(scene.category_label) ||
      this.stringValue(scene.категория) ||
      this.stringValue(scene.primary_category) ||
      'Без категории'
    )
  }

  private recommendationText(scene: JsonRecord) {
    const structured = this.asRecord(scene.recommendation)
    const llm = this.asRecord(scene.llm_recommendation)
    const summary = this.stringValue(structured?.summary) || this.stringValue(llm?.summary)
    const explanation = this.stringValue(llm?.explanation)
    const template = this.stringValue(scene.рекомендации_понижения)

    return summary || explanation || template || ''
  }

  private evidenceText(scene: JsonRecord) {
    const evidence = this.asArray(scene.evidence)
      ?.map((item) => this.asRecord(item))
      .filter((item): item is JsonRecord => item !== null)
      .map((item) => this.stringValue(item.reason) || this.stringValue(item.text) || this.stringValue(item.matched_term))
      .filter(Boolean)
      .join('; ')

    return evidence || this.stringValue(scene.policy_basis) || ''
  }

  private needsReview(scene: JsonRecord) {
    return scene.needs_review === true
  }

  private maxRating(details: AnalysisDetails, stats: JsonRecord | null) {
    return this.stringValue(stats?.максимальный_рейтинг) || details.maxRating || 'нет данных'
  }

  private statusLabel(status: string) {
    const labels: Record<string, string> = {
      QUEUED: 'В очереди',
      PROCESSING: 'В работе',
      DONE: 'Готово',
      FAILED: 'Ошибка',
      DEAD_LETTER: 'Требует ручного retry',
      CANCELLED: 'Отменён'
    }

    return labels[status] ?? status
  }

  private higherRating(left: string, right: string) {
    const order = ['0+', '6+', '12+', '16+', '18+']
    return order.indexOf(right) > order.indexOf(left) ? right : left
  }

  private value(record: JsonRecord | null, key: string) {
    const value = record?.[key]
    return typeof value === 'string' || typeof value === 'number' ? value : null
  }

  private asRecord(value: unknown): JsonRecord | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return null
    }

    return value as JsonRecord
  }

  private asArray(value: unknown): unknown[] | null {
    return Array.isArray(value) ? value : null
  }

  private stringValue(value: unknown) {
    return typeof value === 'string' ? value.trim() : ''
  }

  private truncate(value: string, limit: number) {
    return value.length > limit ? `${value.slice(0, limit - 1)}...` : value
  }

  private dateLabel(value: Date) {
    return new Intl.DateTimeFormat('ru-RU').format(value)
  }

  private dateTimeLabel(value: Date) {
    return new Intl.DateTimeFormat('ru-RU', {
      dateStyle: 'medium',
      timeStyle: 'short'
    }).format(value)
  }

  private exportFileName(details: AnalysisDetails) {
    const baseName = details.fileName.replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9а-яА-ЯёЁ_-]+/g, '-').replace(/-+/g, '-')
    const cleanName = baseName.slice(0, 64).replace(/^-|-$/g, '') || 'analysis'
    return `clean-frame-${cleanName}-${details.id.slice(0, 8)}.pdf`
  }

  private resolveFonts() {
    const regular = join(process.cwd(), 'assets', 'fonts', 'DejaVuSans.ttf')
    const bold = join(process.cwd(), 'assets', 'fonts', 'DejaVuSans-Bold.ttf')

    if (!existsSync(regular) || !existsSync(bold)) {
      throw new InternalServerErrorException('PDF-шрифты не найдены в backend/assets/fonts')
    }

    return { regular, bold }
  }
}
