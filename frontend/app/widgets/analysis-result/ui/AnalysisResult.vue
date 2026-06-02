<script setup lang="ts">
import anime from 'animejs'
import { computed, onMounted, ref, useTemplateRef, watch } from 'vue'
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
const selectedSuggestionIndexes = ref<Record<number, number>>({})
const isCategoryJumpOpen = ref(false)
const isCategoryFilterOpen = ref(false)
const selectedCategoryKeys = ref<string[]>([])
const showAllRawScenes = ref(false)

const scenes = computed(() =>
  props.result?.все_подозрительные_сцены ?? props.result?.обработанные_сцены ?? []
)
const analysisMetadata = computed(() => props.result?.metadata ?? {})
const analysisTargetRating = computed(() => {
  const value = analysisMetadata.value.target_rating
  return typeof value === 'string' && value ? value : null
})
const isTargetedMode = computed(() => Boolean(analysisTargetRating.value))
const targetBlockingTotal = computed(() => {
  const value = analysisMetadata.value.target_blocking_count
  if (typeof value === 'number') {
    return value
  }

  return allPresentedScenes.value.filter((item) => item.scene.exceeds_target).length
})
const allPresentedScenes = computed(() =>
  scenes.value.map((scene, originalIndex) => ({
    ...presentScene(scene),
    originalIndex
  }))
)
const presentedScenes = computed(() => {
  if (!isTargetedMode.value || showAllRawScenes.value) {
    return allPresentedScenes.value
  }

  return allPresentedScenes.value.filter((item) => item.scene.exceeds_target)
})
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
const activeCategoryKeys = computed(() => new Set(selectedCategoryKeys.value))
const hasCategoryFilter = computed(() => selectedCategoryKeys.value.length > 0)
const filteredCategoryGroups = computed(() => {
  if (!hasCategoryFilter.value) {
    return categoryGroups.value
  }

  return categoryGroups.value.filter((group) => activeCategoryKeys.value.has(group.key))
})
const filteredPresentedScenes = computed(() => {
  if (!hasCategoryFilter.value) {
    return presentedScenes.value
  }

  return presentedScenes.value.filter((item) => {
    const key = item.scene.primary_category ?? item.scene.category_id ?? item.scene.категория
    return activeCategoryKeys.value.has(key)
  })
})

const maxRating = computed(() => props.result?.статистика?.максимальный_рейтинг ?? 'нет данных')
const processingTime = computed(() => props.result?.статистика?.время_обработки ?? 0)
const targetLabel = computed(() => analysisTargetRating.value ? `Цель ${analysisTargetRating.value}` : 'Raw-анализ')
const suspiciousTotal = computed(() =>
  props.result?.статистика?.всего_подозрительных ??
  props.result?.статистика?.обработано_подозрительных ??
  scenes.value.length
)
const needsReviewTotal = computed(() => presentedScenes.value.filter((item) => item.scene.needs_review).length)
const fallbackTotal = computed(() => presentedScenes.value.filter((item) => item.scene.fallback_used).length)
const visibleScenesTotal = computed(() => filteredPresentedScenes.value.length)

function revealHiddenElements() {
  rootRef.value?.querySelectorAll('.opacity-0').forEach((element) => {
    element.classList.remove('opacity-0')
  })
}

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

    if (prefersReducedMotion()) {
      panel.classList.remove('opacity-0')
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

function categorySectionId(key: string) {
  return `category-${key.replace(/[^a-zA-Z0-9_-]+/g, '-')}`
}

function selectCategory(key: string) {
  requestAnimationFrame(() => {
    rootRef.value?.querySelector(`#${categorySectionId(key)}`)?.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    })
  })
}

function jumpToCategory(key: string) {
  isCategoryJumpOpen.value = false
  requestAnimationFrame(() => {
    selectCategory(key)
  })
}

function scrollToReportTop() {
  document.querySelector('#report-top')?.scrollIntoView({
    behavior: 'smooth',
    block: 'start'
  })
}

function scrollToSummary() {
  rootRef.value?.querySelector('[data-analysis-summary]')?.scrollIntoView({
    behavior: 'smooth',
    block: 'start'
  })
}

function scrollToCategories() {
  rootRef.value?.querySelector('[data-category-nav]')?.scrollIntoView({
    behavior: 'smooth',
    block: 'start'
  })
}

function toggleCategoryFilter() {
  isCategoryFilterOpen.value = !isCategoryFilterOpen.value
  if (isCategoryFilterOpen.value) {
    isCategoryJumpOpen.value = false
  }
}

function toggleCategoryJump() {
  isCategoryJumpOpen.value = !isCategoryJumpOpen.value
  if (isCategoryJumpOpen.value) {
    isCategoryFilterOpen.value = false
  }
}

function toggleCategoryKey(key: string) {
  selectedCategoryKeys.value = activeCategoryKeys.value.has(key)
    ? selectedCategoryKeys.value.filter((item) => item !== key)
    : [...selectedCategoryKeys.value, key]
}

function clearCategoryFilter() {
  selectedCategoryKeys.value = []
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

function selectedSuggestionIndex(sceneIndex: number, total: number) {
  const selected = selectedSuggestionIndexes.value[sceneIndex] ?? 0
  return Math.min(Math.max(selected, 0), Math.max(total - 1, 0))
}

function selectSuggestion(sceneIndex: number, suggestionIndex: number) {
  selectedSuggestionIndexes.value = {
    ...selectedSuggestionIndexes.value,
    [sceneIndex]: suggestionIndex
  }
}

function suggestionTabLabel(index: number) {
  return ['Мягко', 'Сильнее', 'Сохранить драму'][index] ?? `Вариант ${index + 1}`
}

function targetRatingExplanation(targetRating: string | undefined) {
  return targetRating ? `Цель ${targetRating}: ориентир, до какого возрастного рейтинга можно снизить сцену после правки.` : ''
}

function needsReviewExplanation() {
  return 'Требует проверки: модель нашла неоднозначный риск, поэтому сцену лучше посмотреть редактору вручную.'
}

function fallbackExplanation() {
  return 'Шаблонная рекомендация: LLM-рекомендация не была получена, поэтому показан безопасный стандартный совет.'
}

function ratingWeight(rating: string | undefined) {
  return ['0+', '6+', '12+', '16+', '18+'].indexOf(rating ?? '0+')
}

function levelLabel(level: number) {
  return ['нет риска', 'слабый сигнал', 'умеренный риск', 'выраженный риск', 'высокий риск'][level] ?? `уровень ${level}`
}

function animateResult() {
  if (!rootRef.value || prefersReducedMotion()) {
    revealHiddenElements()
    return
  }

  createSmoothTimeline()
    .add({
      targets: rootRef.value.querySelectorAll('[data-state]'),
      translateY: [smoothMotion.shortLift, 0],
      opacity: [0, 1],
      delay: anime.stagger(70),
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

watch(
  () => selectedCategoryKeys.value.join('|'),
  () => {
    requestAnimationFrame(revealHiddenElements)
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
      <div data-state data-analysis-summary class="analysis-summary glass-panel overflow-hidden opacity-0">
        <div class="grid md:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
          <div class="p-4 md:p-5">
            <p class="text-xs font-black uppercase tracking-[0.24em] text-steel">Сводка анализа</p>
            <h2 class="mt-2 font-display text-3xl font-semibold text-ink md:text-4xl">{{ maxRating }}</h2>
            <p class="mt-2 max-w-xl text-sm leading-6 text-muted">
              {{ isTargetedMode ? `Фактический рейтинг сценария. В главном списке показаны сцены, которые мешают цели ${analysisTargetRating}.` : 'Максимальный возрастной рейтинг по найденным рискованным сценам.' }}
            </p>
          </div>
          <div class="grid grid-cols-1 border-t border-line bg-milk/42 sm:grid-cols-3 md:border-l md:border-t-0">
            <div data-stat class="border-b border-line p-4 opacity-0 sm:border-b-0 sm:border-r">
              <p class="text-2xl font-black text-steel md:text-3xl">{{ targetLabel }}</p>
              <p class="mt-2 text-xs font-bold uppercase tracking-[0.16em] text-muted">цель</p>
            </div>
            <div data-stat class="border-b border-line p-4 opacity-0 sm:border-b-0 sm:border-r">
              <p class="text-2xl font-black text-signal md:text-3xl">{{ isTargetedMode ? targetBlockingTotal : suspiciousTotal }}</p>
              <p class="mt-2 text-xs font-bold uppercase tracking-[0.16em] text-muted">{{ isTargetedMode ? 'мешают цели' : 'рисков' }}</p>
            </div>
            <div data-stat class="p-4 opacity-0">
              <p class="text-2xl font-black text-brass md:text-3xl">{{ processingTime }}с</p>
              <p class="mt-2 text-xs font-bold uppercase tracking-[0.16em] text-muted">время</p>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="scenes.length"
        data-state
        class="quality-strip glass-panel grid gap-3 p-3 opacity-0 sm:grid-cols-3"
      >
        <div class="quality-chip">
          <span class="quality-chip-value">{{ categoryGroups.length }}</span>
          <span class="quality-chip-label">категорий</span>
        </div>
        <div class="quality-chip">
          <span class="quality-chip-value">{{ needsReviewTotal }}</span>
          <span class="quality-chip-label">требуют проверки</span>
        </div>
        <div class="quality-chip">
          <span class="quality-chip-value">{{ fallbackTotal }}</span>
          <span class="quality-chip-label">шаблонных рекомендаций</span>
        </div>
      </div>

      <div
        v-if="isTargetedMode && scenes.length"
        data-state
        class="glass-panel flex flex-wrap items-center justify-between gap-3 p-3 opacity-0"
      >
        <p class="text-sm font-bold leading-6 text-muted">
          Сейчас показаны сцены, которые превышают цель {{ analysisTargetRating }}. Всего raw-сигналов: {{ scenes.length }}.
        </p>
        <button
          class="raw-toggle-button"
          type="button"
          @click="showAllRawScenes = !showAllRawScenes"
        >
          {{ showAllRawScenes ? 'Показать только блокеры цели' : 'Показать все найденные риски' }}
        </button>
      </div>

      <div v-if="scenes.length === 0" class="rounded-[var(--radius-control)] border border-line bg-milk/70 p-6 text-sm font-bold text-muted shadow-soft">
        Подозрительные элементы не найдены.
      </div>

      <div
        v-else-if="isTargetedMode && presentedScenes.length === 0"
        class="rounded-[var(--radius-control)] border border-line bg-milk/70 p-6 text-sm font-bold text-muted shadow-soft"
      >
        Найденные риски не превышают выбранную цель {{ analysisTargetRating }}. Можно включить raw-сигналы выше, чтобы посмотреть полный диагностический список.
      </div>

      <template v-if="scenes.length && presentedScenes.length">
        <nav class="report-jump-nav glass-panel" aria-label="Быстрая навигация по отчёту">
          <button type="button" @click="scrollToReportTop">К началу</button>
          <button type="button" @click="toggleCategoryJump">Перейти</button>
          <button type="button" @click="toggleCategoryFilter">
            Фильтр<span v-if="hasCategoryFilter"> · {{ selectedCategoryKeys.length }}</span>
          </button>
          <div v-show="isCategoryJumpOpen" class="category-filter-panel">
            <div class="border-b border-line pb-3">
              <p class="text-xs font-black uppercase tracking-[0.16em] text-steel">Перейти к категории</p>
            </div>
            <div class="mt-3 grid gap-2">
              <button
                v-for="group in categoryGroups"
                :key="`jump-${group.key}`"
                class="category-jump-option"
                type="button"
                @click="jumpToCategory(group.key)"
              >
                <span class="block truncate text-sm font-black text-ink">{{ group.label }}</span>
                <span class="block text-xs font-bold text-muted">{{ group.items.length }} сцен · {{ levelLabel(group.maxLevel) }}</span>
              </button>
            </div>
            <p v-if="hasCategoryFilter" class="mt-3 text-xs font-bold text-muted">
              Показаны только категории из активного фильтра.
            </p>
          </div>
          <div v-show="isCategoryFilterOpen" class="category-filter-panel">
            <div class="flex items-center justify-between gap-3 border-b border-line pb-3">
              <p class="text-xs font-black uppercase tracking-[0.16em] text-steel">Фильтр категорий</p>
              <button
                class="category-filter-clear"
                type="button"
                :disabled="!hasCategoryFilter"
                @click="clearCategoryFilter"
              >
                Сброс
              </button>
            </div>
            <div class="mt-3 grid gap-2">
              <label
                v-for="group in categoryGroups"
                :key="`filter-${group.key}`"
                class="category-filter-option"
              >
                <input
                  class="sr-only"
                  type="checkbox"
                  :checked="activeCategoryKeys.has(group.key)"
                  @change="toggleCategoryKey(group.key)"
                >
                <span class="category-filter-check">{{ activeCategoryKeys.has(group.key) ? '✓' : '' }}</span>
                <span class="min-w-0">
                  <span class="block truncate text-sm font-black text-ink">{{ group.label }}</span>
                  <span class="block text-xs font-bold text-muted">{{ group.items.length }} сцен · {{ levelLabel(group.maxLevel) }}</span>
                </span>
              </label>
            </div>
            <p class="mt-3 text-xs font-bold text-muted">
              Показано {{ visibleScenesTotal }} из {{ presentedScenes.length }} сцен.
            </p>
          </div>
        </nav>

        <div data-category-nav class="category-card-grid grid gap-3 scroll-mt-24 md:grid-cols-2 xl:grid-cols-4">
          <button
            v-for="group in filteredCategoryGroups"
            :key="group.key"
            class="category-card border border-line p-4 text-left shadow-soft transition hover:-translate-y-0.5 hover:border-steel"
            type="button"
            @click="selectCategory(group.key)"
          >
            <p class="text-xs font-black uppercase tracking-[0.18em] text-steel">{{ group.label }}</p>
            <p class="mt-3 text-lg font-black text-ink">{{ levelLabel(group.maxLevel) }}</p>
            <p class="mt-2 text-xs font-bold leading-5 text-muted">
              {{ group.items.length }} сцен · максимум {{ group.maxRating }}
            </p>
            <p v-if="group.needsReview" class="mt-3 text-xs font-black uppercase tracking-[0.12em] text-signal">
              Требует проверки
            </p>
            <p class="mt-3 text-xs font-black uppercase tracking-[0.12em] text-steel">
              Перейти к сценам
            </p>
          </button>
        </div>

        <div v-if="hasCategoryFilter && filteredCategoryGroups.length === 0" class="rounded-[var(--radius-control)] border border-line bg-milk/70 p-5 text-sm font-bold text-muted shadow-soft">
          По выбранным категориям сцен нет.
        </div>

        <RiskTimelineChart :items="filteredPresentedScenes" @select-scene="selectScene" />

        <section
          v-for="group in filteredCategoryGroups"
          :key="`section-${group.key}`"
          :id="categorySectionId(group.key)"
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
                    {{ item.levelLabel }}
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
                v-show="isExpanded(item.originalIndex)"
                :data-recommendations="item.originalIndex"
                class="recommendation-card mt-5 border border-line p-4 opacity-0"
              >
                <div
                  v-if="(item.scene.target_rating && item.scene.target_rating !== item.scene.рейтинг) || item.scene.needs_review || item.scene.fallback_used"
                  class="mb-4 flex flex-wrap gap-2"
                >
                  <span
                    v-if="item.scene.target_rating && item.scene.target_rating !== item.scene.рейтинг"
                    class="tag-with-tooltip target-rating-pill inline-flex items-center px-3 py-1 text-xs font-black uppercase tracking-[0.12em]"
                    :aria-label="targetRatingExplanation(item.scene.target_rating)"
                    tabindex="0"
                  >
                    цель {{ item.scene.target_rating }}
                    <span class="tag-tooltip" role="tooltip">
                      {{ targetRatingExplanation(item.scene.target_rating) }}
                    </span>
                  </span>
                  <span
                    v-if="item.scene.needs_review"
                    class="tag-with-tooltip inline-flex items-center rounded-full border border-signal/35 bg-signal/10 px-3 py-1 text-xs font-black uppercase tracking-[0.12em] text-signal"
                    :aria-label="needsReviewExplanation()"
                    tabindex="0"
                  >
                    {{ item.needsReviewLabel }}
                    <span class="tag-tooltip" role="tooltip">
                      {{ needsReviewExplanation() }}
                    </span>
                  </span>
                  <span
                    v-if="item.scene.fallback_used"
                    class="tag-with-tooltip inline-flex items-center rounded-full border border-brass/40 bg-brass/10 px-3 py-1 text-xs font-black uppercase tracking-[0.12em] text-brass"
                    :aria-label="fallbackExplanation()"
                    tabindex="0"
                  >
                    {{ item.fallbackLabel }}
                    <span class="tag-tooltip" role="tooltip">
                      {{ fallbackExplanation() }}
                    </span>
                  </span>
                </div>
                <p class="text-xs font-black uppercase tracking-[0.2em] text-steel">редакционные рекомендации</p>
                <p class="recommendation-summary mt-3 text-sm font-bold leading-6 text-muted">
                  {{ item.recommendationSummary }}
                </p>
                <p
                  v-if="item.recommendationExplanation && item.recommendationExplanation !== item.recommendationSummary"
                  class="recommendation-explanation mt-2 text-sm leading-6 text-ink/75"
                >
                  {{ item.recommendationExplanation }}
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
                  <div class="suggestion-tabs mt-3 grid grid-cols-3 gap-1 rounded-[10px] border border-line bg-paper/72 p-1">
                    <button
                      v-for="(suggestion, suggestionIndex) in item.rewriteSuggestions"
                      :key="`${item.originalIndex}-${suggestion.goal}-${suggestionIndex}`"
                      class="suggestion-tab min-w-0 rounded-[8px] px-2 py-2 text-center text-[11px] font-black uppercase tracking-[0.08em] transition"
                      :class="selectedSuggestionIndex(item.originalIndex, item.rewriteSuggestions.length) === suggestionIndex ? 'bg-white text-ink shadow-soft' : 'text-steel hover:bg-white/50'"
                      type="button"
                      @click.stop="selectSuggestion(item.originalIndex, suggestionIndex)"
                    >
                      {{ suggestionTabLabel(suggestionIndex) }}
                    </button>
                  </div>
                  <section
                    v-if="item.rewriteSuggestions[selectedSuggestionIndex(item.originalIndex, item.rewriteSuggestions.length)]"
                    class="mt-3 rounded-[12px] border border-line bg-white/52 p-3"
                  >
                    <p class="text-sm font-black text-ink">
                      {{ item.rewriteSuggestions[selectedSuggestionIndex(item.originalIndex, item.rewriteSuggestions.length)]?.goal ?? '' }}
                    </p>
                    <dl class="suggestion-detail mt-2 grid gap-2 text-xs leading-5 text-muted">
                      <div>
                        <dt class="font-black uppercase tracking-[0.12em] text-steel">Что изменить</dt>
                        <dd class="mt-1 text-ink">{{ item.rewriteSuggestions[selectedSuggestionIndex(item.originalIndex, item.rewriteSuggestions.length)]?.after ?? '' }}</dd>
                      </div>
                      <div v-if="item.rewriteSuggestions[selectedSuggestionIndex(item.originalIndex, item.rewriteSuggestions.length)]?.rationale">
                        <dt class="font-black uppercase tracking-[0.12em] text-steel">Почему</dt>
                        <dd class="mt-1">{{ item.rewriteSuggestions[selectedSuggestionIndex(item.originalIndex, item.rewriteSuggestions.length)]?.rationale ?? '' }}</dd>
                      </div>
                      <div>
                        <dt class="font-black uppercase tracking-[0.12em] text-steel">Эффект</dt>
                        <dd class="mt-1">{{ item.rewriteSuggestions[selectedSuggestionIndex(item.originalIndex, item.rewriteSuggestions.length)]?.expected_effect ?? '' }}</dd>
                      </div>
                    </dl>
                  </section>
                </div>
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
.quality-strip,
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

.quality-chip {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255, 250, 241, 0.68);
  padding: 12px 14px;
}

.quality-chip-value {
  color: var(--color-ink);
  font-size: 1.4rem;
  font-weight: 900;
  line-height: 1;
}

.quality-chip-label {
  min-width: 0;
  color: var(--color-muted);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.12em;
  line-height: 1.25;
  overflow-wrap: anywhere;
  text-align: right;
  text-transform: uppercase;
}

.report-jump-nav {
  position: fixed;
  right: max(18px, env(safe-area-inset-right));
  bottom: max(18px, env(safe-area-inset-bottom));
  z-index: 20;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  padding: 8px;
  max-width: calc(100vw - 36px);
  width: fit-content;
  box-shadow: 0 18px 36px rgba(33, 43, 41, 0.14);
}

.category-filter-panel {
  position: absolute;
  right: 0;
  bottom: calc(100% + 10px);
  width: min(360px, calc(100vw - 36px));
  max-height: min(440px, calc(100vh - 150px));
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: var(--radius-control);
  background: rgba(255, 250, 241, 0.96);
  box-shadow: 0 22px 46px rgba(33, 43, 41, 0.18);
  padding: 14px;
}

.category-filter-clear {
  min-height: 30px;
  border: 1px solid rgba(33, 43, 41, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.62);
  color: var(--color-steel);
  font-size: 0.68rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  padding: 0 10px;
  text-transform: uppercase;
}

.category-filter-clear:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.category-filter-option,
.category-jump-option {
  display: grid;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(33, 43, 41, 0.1);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.46);
  cursor: pointer;
  padding: 10px;
  transition: background-color 160ms ease, border-color 160ms ease;
}

.category-filter-option {
  grid-template-columns: 28px minmax(0, 1fr);
}

.category-jump-option {
  grid-template-columns: minmax(0, 1fr);
  text-align: left;
}

.category-filter-option:hover,
.category-jump-option:hover {
  border-color: rgba(82, 111, 122, 0.34);
  background: white;
}

.category-filter-check {
  display: inline-flex;
  height: 28px;
  width: 28px;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(82, 111, 122, 0.32);
  border-radius: 8px;
  color: var(--color-steel);
  font-size: 0.9rem;
  font-weight: 900;
}

.report-jump-nav button {
  min-height: 36px;
  border: 1px solid rgba(33, 43, 41, 0.12);
  border-radius: 9px;
  background: rgba(255, 250, 241, 0.82);
  color: var(--color-steel);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  padding: 0 12px;
  text-transform: uppercase;
  transition: background-color 160ms ease, border-color 160ms ease, transform 160ms ease;
}

.report-jump-nav button:hover {
  border-color: rgba(82, 111, 122, 0.42);
  background: white;
  transform: translateY(-1px);
}

.raw-toggle-button {
  min-height: 38px;
  border: 1px solid rgba(33, 43, 41, 0.12);
  border-radius: 9px;
  background: rgba(255, 250, 241, 0.82);
  color: var(--color-steel);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  padding: 0 12px;
  text-transform: uppercase;
  transition: background-color 160ms ease, border-color 160ms ease, transform 160ms ease;
}

.raw-toggle-button:hover {
  border-color: rgba(82, 111, 122, 0.42);
  background: white;
  transform: translateY(-1px);
}

.category-section {
  position: relative;
  z-index: 1;
  scroll-margin-top: 110px;
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

.tag-with-tooltip {
  position: relative;
  cursor: help;
  outline: none;
}

.tag-with-tooltip:focus-visible {
  box-shadow: 0 0 0 3px rgba(82, 111, 122, 0.18);
}

.tag-tooltip {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 0;
  z-index: 30;
  width: min(280px, calc(100vw - 40px));
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 250, 241, 0.98);
  box-shadow: 0 18px 36px rgba(33, 43, 41, 0.16);
  color: var(--color-ink);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0;
  line-height: 1.45;
  opacity: 0;
  padding: 10px 12px;
  pointer-events: none;
  text-align: left;
  text-transform: none;
  transform: translateY(4px);
  transition: opacity 140ms ease, transform 140ms ease;
  white-space: normal;
}

.tag-tooltip::after {
  position: absolute;
  left: 22px;
  bottom: -6px;
  width: 10px;
  height: 10px;
  border-right: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  background: rgba(255, 250, 241, 0.98);
  content: "";
  transform: rotate(45deg);
}

.tag-with-tooltip:hover .tag-tooltip,
.tag-with-tooltip:focus-visible .tag-tooltip {
  opacity: 1;
  transform: translateY(0);
}

.recommendation-card {
  background: rgba(255, 250, 241, 0.74);
}

.category-card,
.category-section,
.scene-card,
.recommendation-card,
.recommendation-summary,
.recommendation-explanation,
.suggestion-detail,
.suggestion-detail dd,
.suggestion-tab {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: normal;
}

.suggestion-tabs {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.suggestion-tab {
  min-height: 42px;
  white-space: normal;
  line-height: 1.15;
}

@media (max-width: 640px) {
  .report-jump-nav {
    right: 12px;
    bottom: 12px;
    left: 12px;
    justify-content: center;
    max-width: none;
    width: auto;
  }

  .report-jump-nav button {
    flex: 1 1 auto;
  }

  .category-filter-panel {
    right: 0;
    left: 0;
    width: auto;
  }
}

</style>
