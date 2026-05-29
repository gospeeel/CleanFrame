<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'
import { useRoute } from '#app'
import { presentScene } from '~/entities/analysis'
import type { AnalysisDetails, AnalysisResult } from '~/entities/analysis'
import { useAnalysisDetailsQuery } from '~/features/script-analysis'

const route = useRoute()
const analysisId = computed(() => {
  const value = route.query.id
  return Array.isArray(value) ? value[0] ?? '' : value ?? ''
})
const detailsQuery = useAnalysisDetailsQuery(() => analysisId.value)
const analysis = computed(() => detailsQuery.data.value as AnalysisDetails | undefined)
const result = computed(() => analysis.value?.result as AnalysisResult | null | undefined)
const scenes = computed(() =>
  result.value?.все_подозрительные_сцены ?? result.value?.обработанные_сцены ?? []
)
const presentedScenes = computed(() => scenes.value.map((scene, index) => ({
  ...presentScene(scene),
  index: index + 1
})))
const categoryGroups = computed(() => {
  const groups = new Map<string, {
    label: string
    count: number
    maxRating: string
    maxLevel: number
  }>()

  for (const item of presentedScenes.value) {
    const key = item.scene.primary_category ?? item.scene.category_id ?? item.scene.категория
    const existing = groups.get(key)
    const current = existing ?? {
      label: item.categoryLabel,
      count: 0,
      maxRating: item.scene.рейтинг,
      maxLevel: 0
    }

    current.count += 1
    current.maxLevel = Math.max(current.maxLevel, item.scene.уровень ?? 0)
    current.maxRating = ratingWeight(item.scene.рейтинг) > ratingWeight(current.maxRating)
      ? item.scene.рейтинг
      : current.maxRating
    groups.set(key, current)
  }

  return Array.from(groups.values()).sort((left, right) => right.maxLevel - left.maxLevel || right.count - left.count)
})
const metadata = computed(() => {
  const meta = result.value?.metadata as Record<string, unknown> | undefined
  const rubert = toRecord(meta?.rubert)
  const qwen = toRecord(meta?.qwen)

  return [
    { label: 'RuBERT', value: stringifyMeta(rubert?.model_name ?? rubert?.model_version) },
    { label: 'Qwen', value: stringifyMeta(qwen?.model_name) },
    { label: 'Policy', value: stringifyMeta(meta?.policy_version) },
    { label: 'Taxonomy', value: stringifyMeta(meta?.taxonomy_version) }
  ].filter((item) => item.value !== '-')
})
const maxRating = computed(() => result.value?.статистика?.максимальный_рейтинг ?? analysis.value?.maxRating ?? '-')
const riskCount = computed(() =>
  result.value?.статистика?.всего_подозрительных ??
  result.value?.статистика?.обработано_подозрительных ??
  analysis.value?.riskCount ??
  scenes.value.length
)
const processingTime = computed(() => result.value?.статистика?.время_обработки ?? analysis.value?.processingTime ?? null)
const canPrint = computed(() => Boolean(analysis.value && result.value && !detailsQuery.isPending.value))

watch(canPrint, async (ready) => {
  if (!ready || !process.client) {
    return
  }

  await nextTick()
  window.setTimeout(() => window.print(), 350)
}, { immediate: true })

function printReport() {
  if (process.client) {
    window.print()
  }
}

function ratingWeight(rating: string | undefined) {
  return ['0+', '6+', '12+', '16+', '18+'].indexOf(rating ?? '0+')
}

function formatDate(value: string | null | undefined) {
  if (!value) {
    return '-'
  }

  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(new Date(value))
}

function toRecord(value: unknown) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function stringifyMeta(value: unknown) {
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value)
  }

  return '-'
}
</script>

<template>
  <main class="print-page">
    <div class="print-toolbar">
      <NuxtLink class="toolbar-button" :to="analysisId ? `/report?id=${analysisId}` : '/report'">Назад</NuxtLink>
      <button class="toolbar-button toolbar-button-primary" type="button" :disabled="!canPrint" @click="printReport">
        Печать PDF
      </button>
    </div>

    <section v-if="detailsQuery.isPending.value" class="print-sheet print-state">
      Подготавливаем печатный отчёт...
    </section>
    <section v-else-if="detailsQuery.isError.value || !analysis" class="print-sheet print-state print-error">
      Не удалось загрузить отчёт для печати.
    </section>

    <article v-else class="print-sheet">
      <header class="print-cover">
        <div>
          <p class="brand-kicker">Clean Frame</p>
          <h1>Отчёт возрастного анализа</h1>
          <p class="print-subtitle">{{ analysis.fileName }}</p>
        </div>
        <div class="rating-badge">
          <span>Максимальный рейтинг</span>
          <strong>{{ maxRating }}</strong>
        </div>
      </header>

      <section class="summary-grid">
        <div>
          <span>Рискованных сцен</span>
          <strong>{{ riskCount }}</strong>
        </div>
        <div>
          <span>Требуют проверки</span>
          <strong>{{ analysis.reviewCount }}</strong>
        </div>
        <div>
          <span>Время анализа</span>
          <strong>{{ processingTime ?? '-' }}<small v-if="processingTime !== null">с</small></strong>
        </div>
        <div>
          <span>Дата отчёта</span>
          <strong class="summary-date">{{ formatDate(analysis.createdAt) }}</strong>
        </div>
      </section>

      <section v-if="metadata.length" class="print-section metadata-section">
        <h2>Версии и политика</h2>
        <dl>
          <div v-for="item in metadata" :key="item.label">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </section>

      <section class="print-section">
        <h2>Сводка по категориям</h2>
        <div v-if="categoryGroups.length" class="category-grid">
          <article v-for="group in categoryGroups" :key="group.label" class="category-card">
            <span>{{ group.label }}</span>
            <strong>{{ group.count }} сцен</strong>
            <small>максимум {{ group.maxRating }}</small>
          </article>
        </div>
        <p v-else class="empty-text">Подозрительные элементы не найдены.</p>
      </section>

      <section v-if="presentedScenes.length" class="print-section">
        <h2>Рискованные сцены</h2>
        <article v-for="item in presentedScenes" :key="`${item.index}-${item.scene.текст_сцены}`" class="scene-print-card">
          <div class="scene-print-head">
            <span>#{{ item.index }} · {{ item.categoryLabel }} · {{ item.levelLabel }}</span>
            <strong>{{ item.scene.рейтинг }}</strong>
          </div>
          <p class="scene-text">{{ item.scene.текст_сцены }}</p>

          <div v-if="item.evidence.length" class="scene-block">
            <h3>Основания</h3>
            <ul>
              <li v-for="evidence in item.evidence" :key="`${evidence.category}-${evidence.matched_term}-${evidence.text}`">
                <b>{{ evidence.text }}</b>
                <span>{{ evidence.category_label }}: {{ evidence.reason }}</span>
              </li>
            </ul>
          </div>

          <div class="scene-block">
            <h3>Рекомендация</h3>
            <p class="recommendation-text">{{ item.scene.рекомендации_понижения }}</p>
          </div>

          <div v-if="item.rewriteSuggestions.length" class="scene-block rewrite-block">
            <h3>Варианты правок</h3>
            <div v-for="suggestion in item.rewriteSuggestions" :key="`${suggestion.goal}-${suggestion.before}`" class="rewrite-item">
              <strong>{{ suggestion.goal }}</strong>
              <dl>
                <div>
                  <dt>Было</dt>
                  <dd>{{ suggestion.before }}</dd>
                </div>
                <div>
                  <dt>Стало</dt>
                  <dd>{{ suggestion.after }}</dd>
                </div>
                <div>
                  <dt>Эффект</dt>
                  <dd>{{ suggestion.expected_effect }}</dd>
                </div>
              </dl>
            </div>
          </div>
        </article>
      </section>
    </article>
  </main>
</template>

<style scoped>
.print-page {
  min-height: 100vh;
  background:
    linear-gradient(135deg, rgba(82, 111, 122, 0.08), transparent 42%),
    var(--color-paper);
  color: var(--color-ink);
  padding: 28px;
}

.print-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin: 0 auto 18px;
  max-width: 980px;
}

.toolbar-button {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 250, 241, 0.82);
  color: var(--color-ink);
  font-size: 0.82rem;
  font-weight: 900;
  padding: 10px 14px;
}

.toolbar-button-primary {
  background: var(--color-steel);
  color: white;
}

.toolbar-button:disabled {
  opacity: 0.5;
}

.print-sheet {
  max-width: 980px;
  margin: 0 auto;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255, 250, 241, 0.96);
  box-shadow: 0 24px 80px rgba(50, 58, 54, 0.14);
  padding: 34px;
}

.print-state {
  color: var(--color-muted);
  font-weight: 900;
}

.print-error {
  color: var(--color-signal);
}

.print-cover {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 24px;
  border-bottom: 2px solid var(--line);
  padding-bottom: 26px;
}

.brand-kicker,
.print-section h2,
.scene-print-head span,
.summary-grid span,
.metadata-section dt,
.category-card span,
.scene-block h3,
.rewrite-item dt {
  color: var(--color-steel);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.print-cover h1 {
  margin: 12px 0 0;
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 2.8rem;
  line-height: 1.02;
}

.print-subtitle {
  margin-top: 14px;
  overflow-wrap: anywhere;
  color: var(--color-muted);
  font-size: 1rem;
  font-weight: 800;
  line-height: 1.6;
}

.rating-badge {
  display: grid;
  align-content: center;
  border: 1px solid rgba(82, 111, 122, 0.24);
  border-radius: 16px;
  background:
    linear-gradient(145deg, rgba(82, 111, 122, 0.13), rgba(184, 146, 93, 0.13)),
    rgba(255, 250, 241, 0.82);
  padding: 18px;
}

.rating-badge span {
  color: var(--color-muted);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.rating-badge strong {
  margin-top: 10px;
  color: var(--color-signal);
  font-family: var(--font-display);
  font-size: 3.2rem;
  line-height: 1;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 22px;
}

.summary-grid div,
.category-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(248, 242, 232, 0.68);
  padding: 14px;
}

.summary-grid strong {
  display: block;
  margin-top: 8px;
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 1.8rem;
}

.summary-grid small {
  font-size: 0.8rem;
}

.summary-date {
  font-family: inherit !important;
  font-size: 0.98rem !important;
  line-height: 1.4;
}

.print-section {
  margin-top: 28px;
  page-break-inside: avoid;
}

.print-section h2 {
  margin-bottom: 12px;
}

.metadata-section dl {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.metadata-section div {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px;
}

.metadata-section dd {
  margin-top: 8px;
  overflow-wrap: anywhere;
  color: var(--color-ink);
  font-size: 0.86rem;
  font-weight: 800;
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.category-card strong,
.category-card small {
  display: block;
  margin-top: 8px;
}

.category-card strong {
  color: var(--color-ink);
  font-size: 1rem;
}

.category-card small {
  color: var(--color-muted);
  font-weight: 800;
}

.empty-text {
  color: var(--color-muted);
  font-weight: 800;
}

.scene-print-card {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(255, 250, 241, 0.7);
  margin-top: 14px;
  padding: 16px;
  page-break-inside: avoid;
}

.scene-print-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.scene-print-head strong {
  border: 1px solid rgba(82, 111, 122, 0.24);
  border-radius: 999px;
  color: var(--color-blue);
  padding: 5px 10px;
}

.scene-text {
  margin-top: 14px;
  color: var(--color-ink);
  font-size: 0.92rem;
  font-weight: 700;
  line-height: 1.7;
}

.scene-block {
  border-top: 1px solid var(--line);
  margin-top: 14px;
  padding-top: 12px;
}

.scene-block ul {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.scene-block li,
.rewrite-item {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(248, 242, 232, 0.58);
  padding: 10px;
}

.scene-block li span {
  display: block;
  color: var(--color-muted);
  font-size: 0.78rem;
  font-weight: 800;
  margin-top: 4px;
}

.recommendation-text,
.rewrite-item dd {
  color: var(--color-muted);
  font-size: 0.86rem;
  font-weight: 800;
  line-height: 1.6;
  margin-top: 8px;
  white-space: pre-line;
}

.rewrite-block {
  display: grid;
  gap: 10px;
}

.rewrite-item dl {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

@media (max-width: 760px) {
  .print-page {
    padding: 12px;
  }

  .print-cover,
  .summary-grid,
  .metadata-section dl,
  .category-grid {
    grid-template-columns: 1fr;
  }
}

@media print {
  @page {
    margin: 14mm;
    size: A4;
  }

  .print-page {
    background: white;
    padding: 0;
  }

  .print-toolbar {
    display: none;
  }

  .print-sheet {
    border: 0;
    border-radius: 0;
    box-shadow: none;
    max-width: none;
    padding: 0;
  }

  .print-cover h1 {
    font-size: 30pt;
  }

  .rating-badge strong {
    font-size: 38pt;
  }
}
</style>
