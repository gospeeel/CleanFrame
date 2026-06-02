export interface RatingStats {
  всего_элементов?: number
  всего_подозрительных?: number
  обработано_подозрительных?: number
  сцен_с_максимальным_рейтингом?: number
  сцен_требующих_проверки?: number
  максимальный_рейтинг?: string
  время_обработки?: number
}

export interface LlmRecommendation {
  summary?: string
  explanation: string
  risk_factors: string[]
  rewrite_suggestions: Array<string | RewriteSuggestion>
  self_check_passed?: boolean
  uncertainty_note?: string | null
}

export interface RewriteSuggestion {
  goal: string
  before: string
  after: string
  rationale: string
  expected_effect: string
}

export interface RecommendationSummary {
  summary: string
  rewrite_suggestions: RewriteSuggestion[]
  fallback_used: boolean
  self_check_passed: boolean
}

export interface EvidenceItem {
  category: string
  category_label: string
  text: string
  matched_term: string
  reason: string
}

export interface SuspiciousScene {
  scene_id?: number | string | null
  scene_header?: string | null
  page?: number | null
  element_index?: number | null
  timeline_position?: number | null
  text?: string
  текст_сцены: string
  risk_detected?: boolean
  rating?: string
  рейтинг: string
  target_rating?: string
  analysis_target_rating?: string | null
  exceeds_target?: boolean
  target_delta?: number
  recommendation_skipped_reason?: string | null
  индекс_рейтинга: number
  категория: string
  category_id?: string
  category_label?: string
  primary_category?: string
  secondary_categories?: string[]
  category_labels?: Record<string, string>
  уровень: number
  level_label?: string
  confidence?: {
    category?: number
    level?: number
    rating?: number
  }
  category_scores?: Record<string, number>
  evidence?: EvidenceItem[]
  evidence_meta?: {
    matched_terms?: Record<string, string[]>
    rule_scores?: Record<string, number>
    model_category?: string
  }
  matched_terms?: string[]
  level_scores?: Record<string, number>
  rating_scores?: Record<string, number>
  needs_review?: boolean
  рекомендации_понижения: string
  recommendation?: RecommendationSummary | null
  llm_recommendation?: LlmRecommendation | null
  fallback_used?: boolean
  llm_error?: string | null
  policy_basis?: string | null
}

export interface AnalysisResult {
  обработанные_сцены?: SuspiciousScene[]
  сцены_с_максимальным_рейтингом?: SuspiciousScene[]
  все_подозрительные_сцены?: SuspiciousScene[]
  статистика?: RatingStats
  metadata?: Record<string, unknown>
}

export interface AnalysisResponse {
  detail: string
  result: AnalysisResult
}

export type AnalysisStatus = 'QUEUED' | 'PROCESSING' | 'DONE' | 'FAILED' | 'DEAD_LETTER' | 'CANCELLED'
export type AnalysisTargetRating = 'raw' | '6+' | '12+' | '16+' | '18+'

export interface AnalysisJobResponse {
  id: string
  status: AnalysisStatus
  targetRating: string | null
}

export interface AnalysisListItem {
  id: string
  fileName: string
  status: AnalysisStatus
  maxRating: string | null
  targetRating: string | null
  riskCount: number
  reviewCount: number
  createdAt: string
  completedAt: string | null
  queuedAt: string
  startedAt: string | null
}

export interface AnalysisDetails extends AnalysisListItem {
  processingTime: number | null
  result: AnalysisResult | null
  errorMessage: string | null
  errorCode: string | null
  updatedAt: string
}
