<script setup lang="ts">
import anime from 'animejs'
import { computed, onMounted, useTemplateRef, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { presentScene, useAnalysisUiStore } from '~/entities/analysis'
import type { AnalysisResult } from '~/entities/analysis'
import { createSmoothTimeline, prefersReducedMotion, smoothMotion } from '~/shared/lib/motion'
import RiskTimelineChart from './RiskTimelineChart.vue'

const props = defineProps<{
  result: AnalysisResult | null
  isPending: boolean
  errorMessage: string
}>()

const uiStore = useAnalysisUiStore()
const { expandedSceneIndexes } = storeToRefs(uiStore)
const rootRef = useTemplateRef<HTMLElement>('root')

const scenes = computed(() =>
  props.result?.все_подозрительные_сцены ?? props.result?.обработанные_сцены ?? []
)
const presentedScenes = computed(() =>
  scenes.value.map((scene, originalIndex) => ({
    ...presentScene(scene),
    originalIndex
  }))
)
const categoryGroups = computed(() => {
  const groups = new Map<string, {
    key: string
    label: string
    maxLevel: number
    maxRating: string
    needsReview: boolean
    items: typeof presentedScenes.value
  }>()

  for (const item of presentedScenes.value) {
    const key = item.scene.primary_category ?? item.scene.category_id ?? item.scene.категория
    const existing = groups.get(key)
    const level = item.scene.уровень ?? 0
    const group = existing ?? {
      key,
      label: item.categoryLabel,
      maxLevel: 0,
      maxRating: item.scene.рейтинг,
      needsReview: false,
      items: []
    }

    group.maxLevel = Math.max(group.maxLevel, level)
    group.maxRating = ratingWeight(item.scene.рейтинг) > ratingWeight(group.maxRating)
      ? item.scene.рейтинг
      : group.maxRating
    group.needsReview = group.needsReview || item.scene.needs_review === true
    group.items.push(item)
    groups.set(key, group)
  }

  return [...groups.values()].sort((a, b) => b.maxLevel - a.maxLevel || b.items.length - a.items.length)
})

const maxRating = computed(() => props.result?.статистика?.максимальный_рейтинг ?? 'нет данных')
const processingTime = computed(() => props.result?.статистика?.время_обработки ?? 0)
const suspiciousTotal = computed(() =>
  props.result?.статистика?.всего_подозрительных ??
  props.result?.статистика?.обработано_подозрительных ??
  scenes.value.length
)

function isExpanded(index: number) {
  return expandedSceneIndexes.value.includes(index)
}

function toggleScene(index: number) {
  uiStore.toggleScene(index)

  requestAnimationFrame(() => {
    const panel = rootRef.value?.querySelector(`[data-recommendations="${index}"]`)
    if (!panel) {
      return
    }

    anime({
      targets: panel,
      translateY: [-6, 0],
      opacity: [0, 1],
      duration: smoothMotion.microDuration,
      easing: smoothMotion.easing
    })
  })
}

function selectScene(index: number) {
  if (!expandedSceneIndexes.value.includes(index)) {
    uiStore.toggleScene(index)
  }

  requestAnimationFrame(() => {
    rootRef.value?.querySelector(`[data-scene-index="${index}"]`)?.scrollIntoView({
      behavior: 'smooth',
      block: 'center'
    })
  })
}

function ratingWeight(rating: string | undefined) {
  return ['0+', '6+', '12+', '16+', '18+'].indexOf(rating ?? '0+')
}

function levelLabel(level: number) {
  return ['нет риска', 'слабый сигнал', 'умеренный риск', 'выраженный риск', 'высокий риск'][level] ?? `уровень ${level}`
}

function animateResult() {
  if (!rootRef.value || prefersReducedMotion()) {
    return
  }

  createSmoothTimeline()
    .add({
      targets: rootRef.value.querySelector('[data-state]'),
      translateY: [smoothMotion.shortLift, 0],
      opacity: [0, 1],
      duration: smoothMotion.itemDuration
    })
    .add({
      targets: rootRef.value.querySelectorAll('[data-stat]'),
      translateY: [smoothMotion.mediumLift, 0],
      opacity: [0, 1],
      delay: anime.stagger(85),
      duration: smoothMotion.itemDuration
    }, '-=360')
    .add({
      targets: rootRef.value.querySelectorAll('[data-scene]'),
      translateY: [smoothMotion.mediumLift, 0],
      opacity: [0, 1],
      delay: anime.stagger(smoothMotion.stagger),
      duration: smoothMotion.itemDuration
    }, '-=520')
}

onMounted(animateResult)

watch(
  () => [props.result, props.isPending, props.errorMessage],
  () => {
    requestAnimationFrame(animateResult)
  }
)
</script>

<template>
  <section ref="root" class="space-y-5">
    <div
      v-if="isPending"
      data-state
      class="analysis-state glass-panel relative overflow-hidden p-5 opacity-0 md:p-6"
    >
      <div class="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-signal via-denim to-brass" />
      <div class="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p class="text-xs font-black uppercase tracking-[0.24em] text-steel">Идёт обработка</p>
          <p class="mt-3 font-display text-2xl font-semibold text-ink md:text-3xl">Идёт анализ сценария</p>
          <p class="mt-2 text-sm leading-6 text-muted">Модель обрабатывает сцены и собирает рекомендации.</p>
        </div>
        <div class="flex gap-2">
          <span class="h-3 w-3 animate-pulse rounded-full bg-signal" />
          <span class="h-3 w-3 animate-pulse rounded-full bg-denim [animation-delay:120ms]" />
          <span class="h-3 w-3 animate-pulse rounded-full bg-brass [animation-delay:240ms]" />
        </div>
      </div>
    </div>

    <div
      v-else-if="errorMessage"
      data-state
      class="rounded-[var(--radius-control)] border border-signal/40 bg-signal/10 p-5 text-sm font-bold text-signal opacity-0 shadow-soft"
    >
      {{ errorMessage }}
    </div>

    <template v-else-if="result">
      <div data-state class="analysis-summary glass-panel overflow-hidden opacity-0">
        <div class="grid md:grid-cols-[1.1fr_0.9fr]">
          <div class="p-5 md:p-7">
            <p class="text-xs font-black uppercase tracking-[0.24em] text-steel">Сводка анализа</p>
            <h2 class="mt-3 font-display text-3xl font-semibold text-ink md:text-5xl">{{ maxRating }}</h2>
            <p class="mt-3 max-w-xl text-sm leading-6 text-muted">
              Максимальный возрастной рейтинг по найденным рискованным сценам.
            </p>
          </div>
          <div class="grid grid-cols-1 border-t border-line bg-milk/42 sm:grid-cols-3 md:border-l md:border-t-0">
            <div data-stat class="border-b border-line p-4 opacity-0 sm:border-b-0 sm:border-r md:p-5">
              <p class="text-2xl font-black text-steel md:text-3xl">{{ scenes.length }}</p>
              <p class="mt-2 text-xs font-bold uppercase tracking-[0.16em] text-muted">в выдаче</p>
            </div>
            <div data-stat class="border-b border-line p-4 opacity-0 sm:border-b-0 sm:border-r md:p-5">
              <p class="text-2xl font-black text-signal md:text-3xl">{{ suspiciousTotal }}</p>
              <p class="mt-2 text-xs font-bold uppercase tracking-[0.16em] text-muted">рисков</p>
            </div>
            <div data-stat class="p-4 opacity-0 md:p-5">
              <p class="text-2xl font-black text-brass md:text-3xl">{{ processingTime }}с</p>
              <p class="mt-2 text-xs font-bold uppercase tracking-[0.16em] text-muted">время</p>
            </div>
          </div>
        </div>
      </div>

      <div v-if="scenes.length === 0" class="rounded-[var(--radius-control)] border border-line bg-milk/70 p-6 text-sm font-bold text-muted shadow-soft">
        Подозрительные элементы не найдены.
      </div>

      <template v-if="scenes.length">
        <div class="category-card-grid grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <section
            v-for="group in categoryGroups"
            :key="group.key"
            class="category-card border border-line p-4 shadow-soft"
          >
            <p class="text-xs font-black uppercase tracking-[0.18em] text-steel">{{ group.label }}</p>
            <p class="mt-3 text-lg font-black text-ink">{{ levelLabel(group.maxLevel) }}</p>
            <p class="mt-2 text-xs font-bold leading-5 text-muted">
              {{ group.items.length }} сцен · максимум {{ group.maxRating }}
            </p>
            <p v-if="group.needsReview" class="mt-3 text-xs font-black uppercase tracking-[0.12em] text-signal">
              Требует проверки
            </p>
          </section>
        </div>

        <RiskTimelineChart :items="presentedScenes" @select-scene="selectScene" />

        <section
          v-for="group in categoryGroups"
          :key="`section-${group.key}`"
          class="category-section overflow-hidden border border-line shadow-soft"
        >
          <div class="category-section-header grid gap-3 border-b border-line px-4 py-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end md:px-5">
            <div class="min-w-0">
              <p class="text-xs font-black uppercase tracking-[0.2em] text-steel">категория</p>
              <h3 class="mt-1 break-words font-display text-2xl font-semibold leading-tight text-ink md:text-3xl">{{ group.label }}</h3>
            </div>
            <p class="category-section-meta text-sm font-black text-muted md:text-right">
              {{ group.items.length }} сцен · {{ levelLabel(group.maxLevel) }}
            </p>
          </div>

          <div class="space-y-3 p-3 md:p-4">
            <article
              v-for="item in group.items"
              :key="`${item.scene.текст_сцены}-${item.originalIndex}`"
              :data-scene-index="item.originalIndex"
              data-scene
              class="scene-card group border border-line p-4 opacity-0 shadow-soft transition hover:-translate-y-0.5 hover:bg-white md:p-5"
            >
              <button
                class="grid w-full gap-4 text-left md:grid-cols-[minmax(0,1fr)_auto] md:items-start"
                type="button"
                @click="toggleScene(item.originalIndex)"
              >
                <span class="min-w-0">
                  <span class="block text-xs font-black uppercase tracking-[0.2em] text-steel">
                    {{ item.categoryLabel }} · {{ item.levelLabel }}
                  </span>
                  <span
                    v-if="item.secondaryLabels.length"
                    class="mt-2 block text-xs font-bold leading-5 text-muted"
                  >
                    Доп. фактор: {{ item.secondaryLabels.join(', ') }}
                  </span>
                  <span class="mt-3 flex flex-wrap gap-2">
                    <span class="rating-pill inline-flex items-center px-3 py-1 text-sm font-black">
                      {{ item.scene.рейтинг }}
                    </span>
                    <span
                      v-if="item.scene.target_rating && item.scene.target_rating !== item.scene.рейтинг"
                      class="target-rating-pill inline-flex items-center px-3 py-1 text-xs font-black uppercase tracking-[0.12em]"
                    >
                      цель {{ item.scene.target_rating }}
                    </span>
                    <span
                      v-if="item.scene.needs_review"
                      class="inline-flex items-center rounded-full border border-signal/35 bg-signal/10 px-3 py-1 text-xs font-black uppercase tracking-[0.12em] text-signal"
                    >
                      {{ item.needsReviewLabel }}
                    </span>
                    <span
                      v-if="item.scene.fallback_used"
                      class="inline-flex items-center rounded-full border border-brass/40 bg-brass/10 px-3 py-1 text-xs font-black uppercase tracking-[0.12em] text-brass"
                    >
                      {{ item.fallbackLabel }}
                    </span>
                  </span>
                </span>
                <span
                  class="details-button shrink-0 justify-self-start rounded-[10px] border border-line bg-paper/72 px-3 py-2 text-xs font-black uppercase tracking-[0.14em] text-steel transition group-hover:border-steel md:justify-self-end"
                >
                  {{ isExpanded(item.originalIndex) ? 'Свернуть' : 'Подробнее' }}
                </span>
              </button>

              <p class="mt-5 max-w-5xl text-sm leading-7 text-ink/75">{{ item.scene.текст_сцены }}</p>

              <div
                v-if="isExpanded(item.originalIndex)"
                :data-recommendations="item.originalIndex"
                class="recommendation-card mt-5 border border-line p-4 opacity-0"
              >
                <p class="text-xs font-black uppercase tracking-[0.2em] text-steel">редакционные рекомендации</p>
                <p class="mt-3 whitespace-pre-line text-sm leading-7 text-muted">
                  {{ item.scene.рекомендации_понижения }}
                </p>
                <div v-if="item.evidence.length" class="mt-4 border-t border-line pt-4">
                  <p class="text-xs font-black uppercase tracking-[0.18em] text-steel">основания</p>
                  <ul class="mt-3 space-y-2">
                    <li
                      v-for="evidence in item.evidence"
                      :key="`${evidence.category}-${evidence.matched_term}-${evidence.text}`"
                      class="rounded-[10px] border border-line bg-paper/58 px-3 py-2 text-xs font-bold leading-5 text-muted"
                    >
                      <span class="text-ink">{{ evidence.text }}</span>
                      <span class="block text-steel">{{ evidence.category_label }}: {{ evidence.reason }}</span>
                    </li>
                  </ul>
                </div>
                <div v-if="item.rewriteSuggestions.length" class="mt-4 border-t border-line pt-4">
                  <p class="text-xs font-black uppercase tracking-[0.18em] text-steel">варианты замены</p>
                  <div class="mt-3 space-y-3">
                    <section
                      v-for="suggestion in item.rewriteSuggestions"
                      :key="`${suggestion.goal}-${suggestion.before}`"
                      class="rounded-[12px] border border-line bg-white/52 p-3"
                    >
                      <p class="text-sm font-black text-ink">{{ suggestion.goal }}</p>
                      <dl class="mt-2 space-y-2 text-xs leading-5 text-muted">
                        <div>
                          <dt class="font-black uppercase tracking-[0.12em] text-steel">было</dt>
                          <dd class="mt-1">{{ suggestion.before }}</dd>
                        </div>
                        <div>
                          <dt class="font-black uppercase tracking-[0.12em] text-steel">стало</dt>
                          <dd class="mt-1 text-ink">{{ suggestion.after }}</dd>
                        </div>
                        <div>
                          <dt class="font-black uppercase tracking-[0.12em] text-steel">эффект</dt>
                          <dd class="mt-1">{{ suggestion.expected_effect }}</dd>
                        </div>
                      </dl>
                    </section>
                  </div>
                </div>
                <p v-if="item.scene.policy_basis" class="mt-4 border-t border-line pt-4 text-xs font-bold leading-6 text-steel">
                  {{ item.scene.policy_basis }}
                </p>
              </div>
            </article>
          </div>
        </section>
      </template>
    </template>
  </section>
</template>

<style scoped>
.analysis-state,
.analysis-summary,
.scene-card,
.recommendation-card {
  border-radius: var(--radius-control);
}

.analysis-state,
.analysis-summary {
  position: relative;
}

.analysis-state::before,
.analysis-summary::before {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(140deg, rgba(82, 111, 122, 0.1), transparent 38%),
    linear-gradient(320deg, rgba(184, 146, 93, 0.12), transparent 42%);
  content: "";
  pointer-events: none;
}

.analysis-state > *,
.analysis-summary > * {
  position: relative;
}

.scene-card {
  background:
    linear-gradient(135deg, rgba(255, 250, 241, 0.76), rgba(248, 242, 232, 0.64)),
    linear-gradient(90deg, rgba(82, 111, 122, 0.08), transparent 52%);
}

.category-card,
.category-section {
  border-radius: var(--radius-control);
  background:
    linear-gradient(180deg, rgba(255, 250, 241, 0.92), rgba(248, 242, 232, 0.78)),
    linear-gradient(120deg, rgba(82, 111, 122, 0.06), transparent 46%);
}

.category-card {
  min-height: 126px;
}

.category-section {
  position: relative;
  z-index: 1;
}

.category-section-header {
  background: rgba(255, 250, 241, 0.62);
}

.category-section-meta {
  max-width: 100%;
  overflow-wrap: anywhere;
}

.details-button {
  white-space: nowrap;
}

.rating-pill {
  border-radius: 999px;
  border: 1px solid rgba(82, 111, 122, 0.26);
  background: rgba(82, 111, 122, 0.12);
  color: var(--color-blue);
}

.target-rating-pill {
  border-radius: 999px;
  border: 1px solid rgba(184, 146, 93, 0.38);
  background: rgba(184, 146, 93, 0.12);
  color: var(--color-brass);
}

.recommendation-card {
  background: rgba(255, 250, 241, 0.74);
}
</style>
