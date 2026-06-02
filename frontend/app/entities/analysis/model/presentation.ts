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
  recommendationSummary: string
  recommendationExplanation: string
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
  const rawCategoryLabel = scene.category_label ?? scene.category_labels?.[primaryCategory]
  const categoryLabel = rawCategoryLabel && !looksEnglish(rawCategoryLabel)
    ? rawCategoryLabel
    : formatCategory(primaryCategory)
  const secondaryLabels = (scene.secondary_categories ?? [])
    .map((category) => {
      const label = scene.category_labels?.[category]
      return label && !looksEnglish(label) ? label : formatCategory(category)
    })
    .filter((label) => label !== categoryLabel)
  const evidence = (scene.evidence ?? []).map((item) => ({
    ...item,
    category_label: item.category_label && !looksEnglish(item.category_label)
      ? item.category_label
      : formatCategory(item.category)
  }))

  const rewriteSuggestions = normalizeRewriteSuggestions(scene)
  const recommendationSummary = normalizeRecommendationSummary(scene, categoryLabel)
  const recommendationExplanation = normalizeRecommendationExplanation(scene)

  return {
    scene,
    categoryLabel,
    levelLabel: formatRiskLevel(scene.уровень, scene.level_label),
    secondaryLabels: [...new Set(secondaryLabels)],
    evidence,
    rewriteSuggestions,
    recommendationSummary,
    recommendationExplanation,
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

function normalizeRecommendationSummary(scene: SuspiciousScene, categoryLabel: string) {
  const summary = scene.recommendation?.summary ?? scene.llm_recommendation?.summary ?? ''
  const clean = stripPolicyNoise(summary).trim()

  if (!clean || looksEnglish(clean)) {
    const targetRating = scene.target_rating ?? scene.rating ?? scene.рейтинг
    return `${categoryLabel}: требуется редакционная правка для снижения до ${targetRating}.`
  }

  return clean
}

function normalizeRecommendationExplanation(scene: SuspiciousScene) {
  const explanation = scene.llm_recommendation?.explanation ?? ''
  const clean = stripPolicyNoise(explanation).trim()
  return looksEnglish(clean) ? '' : clean
}

function stripPolicyNoise(text: string) {
  return text
    .replace(/\n{0,2}\s*(Основание|ФЗ-436|FZ-436)[\s\S]*$/i, '')
    .replace(/\s+/g, ' ')
}

function looksEnglish(text: string) {
  const latin = (text.match(/[A-Za-z]/g) ?? []).length
  const cyrillic = (text.match(/[А-Яа-яЁё]/g) ?? []).length
  return latin > 8 && latin > cyrillic
}
