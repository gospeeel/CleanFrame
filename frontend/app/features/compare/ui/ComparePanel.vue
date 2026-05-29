<script setup lang="ts">
import anime from 'animejs'
import { computed, onMounted, useTemplateRef } from 'vue'
import type { AnalysisDetails, SuspiciousScene } from '~/entities/analysis'
import { formatCategory } from '~/entities/analysis/model/presentation'
import { useCompareQueries } from '~/features/compare'
import { createSmoothTimeline, prefersReducedMotion, smoothMotion } from '~/shared/lib/motion'

interface Snapshot {
  id: string
  fileName: string
  status: AnalysisDetails['status']
  createdAt: string
  maxRating: string
  riskCount: number
  reviewCount: number
  sceneCount: number
  categories: Record<string, number>
  changedFromBase: {
    rating: boolean
    riskCount: number
    reviewCount: number
    sceneCount: number
    addedCategories: string[]
    removedCategories: string[]
  } | null
}

const rootRef = useTemplateRef<HTMLElement>('root')
const {
  groups,
  selectedFileName,
  selectedIds,
  selectedGroup,
  detailsQuery,
  toggleAnalysis
} = useCompareQueries()

const details = computed(() => detailsQuery.data.value ?? [])
const snapshots = computed(() => {
  const base = details.value[0] ? toSnapshot(details.value[0], null) : null
  return details.value.map((analysis, index) => toSnapshot(analysis, index === 0 ? null : base))
})

const categoryDiffRows = computed(() => {
  const categoryNames = new Set<string>()
  for (const snapshot of snapshots.value) {
    for (const category of Object.keys(snapshot.categories)) {
      categoryNames.add(category)
    }
  }

  return Array.from(categoryNames).sort().map((category) => ({
    category,
    values: snapshots.value.map((snapshot) => snapshot.categories[category] ?? 0)
  }))
})

const selectedIdSet = computed(() => new Set(selectedIds.value))

function toSnapshot(analysis: AnalysisDetails, base: Snapshot | null): Snapshot {
  const scenes = extractScenes(analysis)
  const categories = scenes.reduce<Record<string, number>>((acc, scene) => {
    const category = scene.category_label ?? formatCategory(scene.category_id ?? scene.primary_category ?? scene.категория)
    acc[category] = (acc[category] ?? 0) + 1
    return acc
  }, {})
  const maxRating = analysis.result?.статистика?.максимальный_рейтинг ?? analysis.maxRating ?? '-'

  return {
    id: analysis.id,
    fileName: analysis.fileName,
    status: analysis.status,
    createdAt: analysis.createdAt,
    maxRating,
    riskCount: analysis.riskCount,
    reviewCount: analysis.reviewCount,
    sceneCount: scenes.length,
    categories,
    changedFromBase: base
      ? {
          rating: maxRating !== base.maxRating,
          riskCount: analysis.riskCount - base.riskCount,
          reviewCount: analysis.reviewCount - base.reviewCount,
          sceneCount: scenes.length - base.sceneCount,
          addedCategories: Object.keys(categories).filter((category) => !base.categories[category]),
          removedCategories: Object.keys(base.categories).filter((category) => !categories[category])
        }
      : null
  }
}

function extractScenes(analysis: AnalysisDetails): SuspiciousScene[] {
  return analysis.result?.все_подозрительные_сцены ?? analysis.result?.обработанные_сцены ?? []
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}

function formatDelta(value: number) {
  if (value === 0) {
    return '0'
  }

  return value > 0 ? `+${value}` : String(value)
}

function shouldShowDelta(value: number) {
  return value !== 0
}

function statusLabel(status: AnalysisDetails['status']) {
  if (status === 'DONE') return 'Готово'
  if (status === 'QUEUED') return 'В очереди'
  if (status === 'PROCESSING') return 'В работе'
  if (status === 'FAILED') return 'Ошибка'
  if (status === 'DEAD_LETTER') return 'Требует retry'
  if (status === 'CANCELLED') return 'Отменён'
  return status
}

function canToggle(id: string) {
  return selectedIds.value.length > 2 || !selectedIdSet.value.has(id)
}

onMounted(() => {
  if (!rootRef.value || prefersReducedMotion()) {
    return
  }

  createSmoothTimeline()
    .add({
      targets: rootRef.value.querySelector('[data-compare-title]'),
      translateY: [smoothMotion.mediumLift, 0],
      opacity: [0, 1],
      duration: smoothMotion.enterDuration
    })
    .add({
      targets: rootRef.value.querySelectorAll('[data-compare-card]'),
      translateY: [smoothMotion.shortLift, 0],
      opacity: [0, 1],
      delay: anime.stagger(smoothMotion.stagger),
      duration: smoothMotion.itemDuration
    }, '-=520')
})
</script>

<template>
  <section ref="root" class="page-shell max-w-[1280px] compare-page">
    <div data-compare-title class="mb-6 opacity-0">
      <p class="compare-kicker">Сравнение анализов</p>
      <h1 class="section-title mt-3 font-display font-semibold text-ink">Несколько прогонов одного сценария</h1>
      <p class="mt-4 max-w-2xl text-sm leading-7 text-muted">
        Выберите сценарий из истории и сравните результаты разных запусков по рейтингу, категориям, сценам и версиям моделей.
      </p>
    </div>

    <div v-if="!groups.length && !detailsQuery.isPending.value" data-compare-card class="compare-empty glass-panel opacity-0">
      В истории пока нет сценариев с двумя и более анализами.
    </div>

    <div v-else class="compare-layout">
      <aside data-compare-card class="compare-panel glass-panel opacity-0">
        <p class="compare-kicker">Сценарий</p>
        <select v-model="selectedFileName" class="compare-select">
          <option v-for="group in groups" :key="group.fileName" :value="group.fileName">
            {{ group.fileName }} · {{ group.analyses.length }}
          </option>
        </select>

        <div class="compare-run-list">
          <button
            v-for="analysis in selectedGroup?.analyses ?? []"
            :key="analysis.id"
            class="compare-run"
            :class="{ 'compare-run-active': selectedIdSet.has(analysis.id) }"
            type="button"
            :disabled="!canToggle(analysis.id)"
            @click="toggleAnalysis(analysis.id)"
          >
            <span>{{ formatDate(analysis.createdAt) }}</span>
            <strong>{{ analysis.maxRating ?? analysis.status }}</strong>
            <small>{{ statusLabel(analysis.status) }} · рисков: {{ analysis.riskCount }}</small>
          </button>
        </div>
      </aside>

      <main class="compare-main">
        <div v-if="selectedIds.length < 2" data-compare-card class="compare-empty glass-panel opacity-0">
          Выберите минимум два анализа.
        </div>
        <div v-else-if="detailsQuery.isPending.value" data-compare-card class="compare-empty glass-panel opacity-0">
          Загружаем сравнение...
        </div>
        <div v-else-if="detailsQuery.isError.value" data-compare-card class="compare-empty compare-error glass-panel opacity-0">
          Не удалось загрузить выбранные анализы.
        </div>
        <template v-else>
          <div class="snapshot-grid">
            <article
              v-for="snapshot in snapshots"
              :key="snapshot.id"
              data-compare-card
              class="snapshot-card glass-panel opacity-0"
            >
              <div class="snapshot-head">
                <span>{{ formatDate(snapshot.createdAt) }}</span>
                <NuxtLink :to="`/report?id=${snapshot.id}`">Отчёт</NuxtLink>
              </div>
              <strong class="snapshot-rating">{{ snapshot.maxRating }}</strong>
              <div class="snapshot-metrics">
                <div>
                  <span>Риски</span>
                  <b>{{ snapshot.riskCount }}</b>
                  <em v-if="snapshot.changedFromBase && shouldShowDelta(snapshot.changedFromBase.riskCount)">
                    {{ formatDelta(snapshot.changedFromBase.riskCount) }}
                  </em>
                </div>
                <div>
                  <span>Проверка</span>
                  <b>{{ snapshot.reviewCount }}</b>
                  <em v-if="snapshot.changedFromBase && shouldShowDelta(snapshot.changedFromBase.reviewCount)">
                    {{ formatDelta(snapshot.changedFromBase.reviewCount) }}
                  </em>
                </div>
                <div>
                  <span>Сцены</span>
                  <b>{{ snapshot.sceneCount }}</b>
                  <em v-if="snapshot.changedFromBase && shouldShowDelta(snapshot.changedFromBase.sceneCount)">
                    {{ formatDelta(snapshot.changedFromBase.sceneCount) }}
                  </em>
                </div>
              </div>
              <p v-if="snapshot.changedFromBase?.rating" class="snapshot-note">Рейтинг изменился относительно базового запуска.</p>
            </article>
          </div>

          <section v-if="categoryDiffRows.length" data-compare-card class="compare-table glass-panel opacity-0">
            <div class="compare-table-head">
              <p class="compare-kicker">Категории</p>
              <span>{{ categoryDiffRows.length }} категорий</span>
            </div>
            <div class="compare-category-row compare-category-head" :style="{ '--compare-cols': snapshots.length }">
              <span>Категория</span>
              <span v-for="snapshot in snapshots" :key="snapshot.id">{{ formatDate(snapshot.createdAt) }}</span>
            </div>
            <div
              v-for="row in categoryDiffRows"
              :key="row.category"
              class="compare-category-row"
              :style="{ '--compare-cols': snapshots.length }"
            >
              <strong>{{ row.category }}</strong>
              <span v-for="(value, index) in row.values" :key="`${row.category}-${index}`">{{ value }}</span>
            </div>
          </section>
          <section v-else data-compare-card class="compare-empty compare-empty-compact glass-panel opacity-0">
            Категории риска не найдены: выбранные запуски завершились без риск-сцен.
          </section>

          <section data-compare-card class="compare-table glass-panel opacity-0">
            <div class="compare-table-head">
              <p class="compare-kicker">Отличия от первого выбранного анализа</p>
            </div>
            <div class="diff-list">
              <article v-for="snapshot in snapshots.slice(1)" :key="snapshot.id">
                <strong>{{ formatDate(snapshot.createdAt) }}</strong>
                <p>
                  Добавлены категории:
                  {{ snapshot.changedFromBase?.addedCategories.join(', ') || 'нет' }}
                </p>
                <p>
                  Пропали категории:
                  {{ snapshot.changedFromBase?.removedCategories.join(', ') || 'нет' }}
                </p>
              </article>
            </div>
          </section>
        </template>
      </main>
    </div>
  </section>
</template>

<style scoped>
.compare-layout {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  gap: 18px;
}

.compare-kicker {
  color: var(--color-blue);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.22em;
  text-transform: uppercase;
}

.compare-panel,
.snapshot-card,
.compare-table,
.compare-empty {
  border-radius: var(--radius-panel);
}

.compare-panel {
  align-self: start;
  padding: 18px;
}

.compare-select {
  margin-top: 12px;
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 250, 241, 0.78);
  color: var(--color-ink);
  font-weight: 800;
  padding: 11px 12px;
}

.compare-run-list {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.compare-run {
  display: grid;
  gap: 4px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 250, 241, 0.5);
  padding: 12px;
  text-align: left;
  transition: border-color 160ms ease, background 160ms ease, transform 160ms ease;
}

.compare-run:hover:not(:disabled),
.compare-run-active {
  border-color: var(--color-blue);
  background: white;
  transform: translateX(2px);
}

.compare-run:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.compare-run span,
.compare-run small,
.snapshot-head,
.snapshot-metrics span,
.snapshot-metrics em,
.compare-table-head,
.compare-category-head {
  color: var(--color-muted);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.compare-run strong {
  color: var(--color-ink);
  font-size: 1.2rem;
}

.compare-main {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.snapshot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
}

.snapshot-card {
  padding: 18px;
}

.snapshot-head,
.compare-table-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.snapshot-head a {
  color: var(--color-blue);
}

.snapshot-rating {
  display: block;
  margin-top: 18px;
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 2.4rem;
  line-height: 1;
}

.snapshot-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 18px;
}

.snapshot-metrics div {
  display: grid;
  min-height: 80px;
  align-content: space-between;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 250, 241, 0.52);
  padding: 10px;
}

.snapshot-metrics b {
  display: block;
  color: var(--color-ink);
  font-size: 1.15rem;
  line-height: 1;
}

.snapshot-metrics em {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  background: rgba(82, 111, 122, 0.12);
  padding: 3px 6px;
  color: var(--color-blue);
  font-style: normal;
}

.snapshot-note {
  margin-top: 12px;
  color: var(--color-signal);
  font-size: 0.82rem;
  font-weight: 900;
}

.compare-empty-compact {
  padding: 18px;
}

.compare-table {
  overflow: hidden;
}

.compare-table-head {
  border-bottom: 1px solid var(--line);
  padding: 16px;
}

.compare-category-row {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) repeat(var(--compare-cols), minmax(80px, 0.5fr));
  gap: 10px;
  border-bottom: 1px solid var(--line);
  padding: 12px 16px;
}

.compare-category-row:last-child {
  border-bottom: 0;
}

.compare-category-row strong,
.compare-category-row span {
  overflow-wrap: anywhere;
}

.diff-list {
  display: grid;
  gap: 12px;
  padding: 16px;
}

.diff-list article {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 250, 241, 0.46);
  padding: 12px;
}

.diff-list strong {
  color: var(--color-ink);
}

.diff-list p {
  margin-top: 8px;
  color: var(--color-muted);
  font-size: 0.88rem;
  font-weight: 800;
}

.compare-empty {
  padding: 24px;
  color: var(--color-muted);
  font-weight: 900;
}

.compare-error {
  color: var(--color-signal);
}

@media (max-width: 900px) {
  .compare-layout {
    grid-template-columns: 1fr;
  }

  .compare-category-row {
    grid-template-columns: 1fr;
  }
}
</style>
