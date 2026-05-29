import type { EvidenceItem, RewriteSuggestion, SuspiciousScene } from './types'

const CATEGORY_ALIASES: Record<string, string> = {
  scary: 'fear',
  fear: 'fear',
  drugs_alcohol: 'substance',
  substance: 'substance',
  erotic: 'sexual',
  sexual: 'sexual',
  violence: 'violence',
  profanity: 'profanity',
  safe: 'safe'
}

const CATEGORY_LABELS: Record<string, string> = {
  violence: 'Насилие',
  profanity: 'Грубая лексика',
  substance: 'Алкоголь, табак и вещества',
  sexual: 'Интимный контент',
  fear: 'Пугающие сцены',
  safe: 'Без риска'
}

const LEVEL_LABELS: Record<number, string> = {
  0: 'нет риска',
  1: 'слабый сигнал',
  2: 'умеренный риск',
  3: 'выраженный риск',
  4: 'высокий риск'
}

export interface PresentedScene {
  scene: SuspiciousScene
  categoryLabel: string
  levelLabel: string
  secondaryLabels: string[]
  evidence: EvidenceItem[]
  rewriteSuggestions: RewriteSuggestion[]
  needsReviewLabel: string
  fallbackLabel: string
}

export function normalizeCategory(category: string | undefined | null) {
  if (!category) {
    return 'safe'
  }

  return CATEGORY_ALIASES[category] ?? category
}

export function formatCategory(category: string | undefined | null) {
  const normalized = normalizeCategory(category)
  return CATEGORY_LABELS[normalized] ?? category ?? 'Без риска'
}

export function formatRiskLevel(level: number | undefined | null, fallback?: string) {
  if (fallback) {
    return fallback
  }

  if (level === undefined || level === null) {
    return 'риск не определён'
  }

  return LEVEL_LABELS[level] ?? `уровень ${level}`
}

export function presentScene(scene: SuspiciousScene): PresentedScene {
  const primaryCategory = scene.primary_category ?? scene.category_id ?? scene.категория
  const categoryLabel = scene.category_label ?? scene.category_labels?.[primaryCategory] ?? formatCategory(primaryCategory)
  const secondaryLabels = (scene.secondary_categories ?? [])
    .map((category) => scene.category_labels?.[category] ?? formatCategory(category))
    .filter((label) => label !== categoryLabel)

  const rewriteSuggestions = normalizeRewriteSuggestions(scene)

  return {
    scene,
    categoryLabel,
    levelLabel: formatRiskLevel(scene.уровень, scene.level_label),
    secondaryLabels: [...new Set(secondaryLabels)],
    evidence: scene.evidence ?? [],
    rewriteSuggestions,
    needsReviewLabel: 'Требует проверки',
    fallbackLabel: 'Шаблонная рекомендация'
  }
}

function normalizeRewriteSuggestions(scene: SuspiciousScene): RewriteSuggestion[] {
  const structured = scene.recommendation?.rewrite_suggestions
  if (structured?.length) {
    return structured
  }

  const llmSuggestions = scene.llm_recommendation?.rewrite_suggestions ?? []
  return llmSuggestions
    .filter((item): item is RewriteSuggestion => typeof item === 'object' && item !== null)
    .filter((item) => Boolean(item.goal && item.before && item.after))
}
