<script setup lang="ts">
import anime from 'animejs'
import { computed, onMounted, useTemplateRef } from 'vue'
import { useAnalysisListQuery } from '~/features/script-analysis'
import { createSmoothTimeline, prefersReducedMotion, smoothMotion } from '~/shared/lib/motion'
import type { AnalysisListItem } from '~/entities/analysis'

const rootRef = useTemplateRef<HTMLElement>('root')
const historyQuery = useAnalysisListQuery()

function formatAnalysisResult(analysis: AnalysisListItem) {
  const target = analysis.targetRating ? `Цель: ${analysis.targetRating}` : 'Raw-анализ'

  if (analysis.status === 'FAILED') {
    return `${target} · Анализ завершился ошибкой`
  }

  if (analysis.status === 'DEAD_LETTER') {
    return `${target} · Анализ не прошёл после повторных попыток`
  }

  if (analysis.status === 'CANCELLED') {
    return `${target} · Анализ отменён`
  }

  if (analysis.status === 'QUEUED' || analysis.status === 'PROCESSING') {
    return `${target} · Анализ выполняется`
  }

  return `${target} · Возрастной рейтинг: ${analysis.maxRating ?? 'нет данных'} · рисков: ${analysis.riskCount}`
}

const formattedHistory = computed(() =>
  (historyQuery.data.value ?? []).map((item, index) => ({
    id: item.id,
    fileName: item.fileName,
    status: item.status,
    reviewCount: item.reviewCount,
    result: formatAnalysisResult(item),
    marker: `#${String(index + 1).padStart(2, '0')}`,
    formattedDate: new Date(item.createdAt).toLocaleString('ru-RU', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    })
  }))
)

onMounted(() => {
  requestAnimationFrame(() => {
    if (!rootRef.value || prefersReducedMotion()) {
      return
    }

    createSmoothTimeline()
      .add({
        targets: rootRef.value.querySelector('[data-title]'),
        translateY: [smoothMotion.mediumLift, 0],
        opacity: [0, 1],
        duration: smoothMotion.enterDuration
      })
      .add({
        targets: rootRef.value.querySelectorAll('[data-history-row]'),
        translateY: [smoothMotion.shortLift, 0],
        opacity: [0, 1],
        delay: anime.stagger(smoothMotion.stagger),
        duration: smoothMotion.itemDuration
      }, '-=480')
  })
})
</script>

<template>
  <section ref="root" class="page-shell max-w-[1120px]">
    <div data-title class="mb-6 opacity-0">
      <p class="text-xs font-black uppercase tracking-[0.24em] text-steel">История запросов</p>
      <h1 class="section-title mt-3 font-display font-semibold text-ink">История запросов</h1>
      <p class="mt-4 max-w-2xl text-sm leading-7 text-muted">
        Лента последних анализов с сохранёнными результатами и статусами обработки.
      </p>
    </div>

    <div class="history-panel glass-panel overflow-hidden">
      <div class="hidden border-b border-line bg-milk/55 px-5 py-3 text-xs font-black uppercase tracking-[0.18em] text-muted md:grid md:grid-cols-[96px_minmax(0,1fr)_180px]">
        <span>номер</span>
        <span>результат</span>
        <span class="hidden md:block">дата</span>
      </div>

      <ul>
        <li v-if="historyQuery.isPending.value" class="px-5 py-8 text-sm font-bold text-muted">
          Загружаем историю...
        </li>
        <li v-else-if="historyQuery.isError.value" class="px-5 py-8 text-sm font-bold text-signal">
          Не удалось загрузить историю.
        </li>
        <li v-else-if="!formattedHistory.length" class="px-5 py-8 text-sm font-bold text-muted">
          История пока пуста.
        </li>
        <li
          v-for="item in formattedHistory"
          :key="item.id"
          data-history-row
          class="history-row grid gap-3 border-b border-line px-4 py-4 opacity-0 last:border-b-0 sm:px-5 md:grid-cols-[96px_minmax(0,1fr)_180px] md:items-center"
        >
          <span class="history-marker font-display text-xl font-semibold md:text-2xl">{{ item.marker }}</span>
          <NuxtLink
            class="min-w-0 break-words text-sm font-bold text-ink transition hover:text-denim"
            :to="`/report?id=${item.id}`"
          >
            <span class="block">{{ item.fileName }}</span>
            <span class="mt-1 block text-xs font-bold uppercase tracking-[0.12em] text-muted">
              {{ item.result }} · {{ item.status }} · проверка: {{ item.reviewCount }}
            </span>
          </NuxtLink>
          <span class="history-date text-sm font-bold text-muted">{{ item.formattedDate }}</span>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.history-panel {
  position: relative;
  border-radius: var(--radius-panel);
}

.history-panel::before {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(120deg, rgba(82, 111, 122, 0.1), transparent 38%),
    linear-gradient(300deg, rgba(184, 146, 93, 0.12), transparent 44%);
  content: "";
  pointer-events: none;
}

.history-panel > * {
  position: relative;
}

.history-row {
  background: rgba(255, 250, 241, 0.34);
  transition: background 160ms ease, transform 160ms ease;
}

.history-row:hover {
  background: rgba(255, 250, 241, 0.68);
  transform: translateX(3px);
}

.history-marker {
  color: var(--color-blue);
}

.history-date {
  justify-self: start;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 250, 241, 0.58);
  padding: 6px 10px;
}
</style>
