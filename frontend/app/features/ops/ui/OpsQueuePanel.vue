<script setup lang="ts">
import anime from 'animejs'
import { computed, onMounted, useTemplateRef } from 'vue'
import { useOpsQueries } from '~/features/ops'
import { createSmoothTimeline, prefersReducedMotion, smoothMotion } from '~/shared/lib/motion'

const rootRef = useTemplateRef<HTMLElement>('root')
const { summaryQuery, retryMutation } = useOpsQueries()

const summary = computed(() => summaryQuery.data.value)
const statusCards = computed(() => {
  const data = summary.value
  return [
    { label: 'В очереди', value: data?.queued ?? 0, tone: 'queue' },
    { label: 'В работе', value: data?.processing ?? 0, tone: 'processing' },
    { label: 'Ошибки', value: (data?.failed ?? 0) + (data?.deadLetter ?? 0), tone: 'failed' },
    { label: 'Завершено', value: data?.done ?? 0, tone: 'done' }
  ]
})
const queueCards = computed(() => {
  const queue = summary.value?.queue
  return [
    { label: 'Concurrency', value: queue?.concurrency ?? 0 },
    { label: 'Utilization', value: `${Math.round(queue?.utilizationPercent ?? 0)}%` }
  ]
})
const queueBars = computed(() => {
  const queue = summary.value?.queue
  const items = [
    { label: 'Active', value: queue?.active ?? 0, tone: 'active' },
    { label: 'Waiting', value: queue?.waiting ?? 0, tone: 'waiting' },
    { label: 'Delayed', value: queue?.delayed ?? 0, tone: 'delayed' },
    { label: 'Failed', value: queue?.failed ?? 0, tone: 'failed' },
    { label: 'Completed', value: queue?.completed ?? 0, tone: 'completed' }
  ]
  const maxValue = Math.max(...items.map((item) => item.value), 1)

  return items.map((item) => ({
    ...item,
    percent: Math.round((item.value / maxValue) * 100),
    scale: item.value === 0 ? '0' : Math.max(0.08, item.value / maxValue).toFixed(3)
  }))
})
const rows = computed(() => summary.value?.items ?? [])

function formatDuration(ms: number | null | undefined) {
  if (ms === null || ms === undefined) {
    return '-'
  }

  if (ms < 1000) {
    return `${ms} мс`
  }

  const seconds = Math.round(ms / 1000)
  if (seconds < 60) {
    return `${seconds} с`
  }

  return `${Math.floor(seconds / 60)} мин ${seconds % 60} с`
}

function formatDate(value: string | null | undefined) {
  if (!value) {
    return '-'
  }

  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}

function statusLabel(status: string) {
  if (status === 'QUEUED') return 'Очередь'
  if (status === 'PROCESSING') return 'В работе'
  if (status === 'FAILED') return 'Ошибка'
  if (status === 'DEAD_LETTER') return 'Dead-letter'
  if (status === 'CANCELLED') return 'Отменён'
  return 'Готово'
}

onMounted(() => {
  if (!rootRef.value || prefersReducedMotion()) {
    return
  }

  createSmoothTimeline()
    .add({
      targets: rootRef.value.querySelector('[data-ops-title]'),
      translateY: [smoothMotion.mediumLift, 0],
      opacity: [0, 1],
      duration: smoothMotion.enterDuration
    })
    .add({
      targets: rootRef.value.querySelectorAll('[data-ops-card], [data-ops-table]'),
      translateY: [smoothMotion.shortLift, 0],
      opacity: [0, 1],
      delay: anime.stagger(smoothMotion.stagger),
      duration: smoothMotion.itemDuration
    }, '-=520')
})
</script>

<template>
  <section ref="root" class="page-shell max-w-[1280px]">
    <div data-ops-title class="mb-6 opacity-0">
      <p class="text-xs font-black uppercase tracking-[0.24em] text-steel">Admin ops</p>
      <h1 class="section-title mt-3 font-display font-semibold text-ink">Очередь анализа</h1>
      <p class="mt-4 max-w-2xl text-sm leading-7 text-muted">
        Операционная панель для статусов BullMQ/worker, проблемных анализов и ручного повторного запуска.
      </p>
    </div>

    <div class="grid gap-3 md:grid-cols-4">
      <article
        v-for="card in statusCards"
        :key="card.label"
        data-ops-card
        class="ops-card glass-panel opacity-0"
        :data-tone="card.tone"
      >
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
      </article>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-[minmax(0,0.82fr)_minmax(380px,1fr)]">
      <article data-ops-card class="ops-panel ops-panel-compact glass-panel opacity-0">
        <div class="ops-panel-head">
          <div>
            <p class="ops-kicker">Latency</p>
            <h2>Средние значения</h2>
          </div>
          <button class="ops-button" type="button" :disabled="summaryQuery.isFetching.value" @click="summaryQuery.refetch()">
            Обновить
          </button>
        </div>
        <div class="ops-metrics-grid">
          <div>
            <span>Queue latency</span>
            <strong>{{ formatDuration(summary?.averageQueueLatencyMs) }}</strong>
          </div>
          <div>
            <span>Processing time</span>
            <strong>{{ formatDuration(summary?.averageProcessingTimeMs) }}</strong>
          </div>
          <div>
            <span>Всего анализов</span>
            <strong>{{ summary?.total ?? 0 }}</strong>
          </div>
        </div>
      </article>

      <article data-ops-card class="ops-panel glass-panel opacity-0">
        <div class="ops-panel-head">
          <div>
            <p class="ops-kicker">BullMQ</p>
            <h2>Статусы очереди</h2>
          </div>
          <div class="ops-queue-list ops-queue-list-inline">
            <div v-for="item in queueCards" :key="item.label">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </div>
        <div class="ops-bars" aria-label="Статусы очереди BullMQ">
          <div
            v-for="item in queueBars"
            :key="item.label"
            class="ops-bar-row"
            :data-tone="item.tone"
            :style="{ '--bar-scale': item.scale }"
          >
            <div class="ops-bar-meta">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }} · {{ item.percent }}%</strong>
            </div>
            <div
              class="ops-bar-track"
              role="progressbar"
              :aria-label="item.label"
              :aria-valuenow="item.value"
              aria-valuemin="0"
              :aria-valuemax="Math.max(...queueBars.map((bar) => bar.value), 1)"
            >
              <div class="ops-bar-fill" />
            </div>
          </div>
        </div>
      </article>
    </div>

    <section data-ops-table class="ops-table glass-panel mt-4 opacity-0">
      <div class="ops-table-head">
        <div>
          <p class="ops-kicker">Jobs</p>
          <h2>Активные и проблемные анализы</h2>
        </div>
        <span>{{ rows.length }} записей</span>
      </div>

      <div v-if="summaryQuery.isPending.value" class="ops-empty">Загружаем очередь...</div>
      <div v-else-if="summaryQuery.isError.value" class="ops-error">Не удалось загрузить ops-данные.</div>
      <div v-else-if="!rows.length" class="ops-empty">Нет активных, failed или dead-letter задач.</div>
      <div v-else class="ops-rows">
        <article v-for="item in rows" :key="item.id" class="ops-row">
          <div class="ops-row-main">
            <span class="ops-status" :data-status="item.status">{{ statusLabel(item.status) }}</span>
            <NuxtLink class="ops-file" :to="`/report?id=${item.id}`">{{ item.fileName }}</NuxtLink>
            <small>{{ item.userLogin }} · {{ item.userEmail }}</small>
          </div>
          <div class="ops-row-meta">
            <span>attempts: {{ item.attempts }}</span>
            <span>queued: {{ formatDate(item.queuedAt) }}</span>
            <span>worker: {{ item.workerId ?? '-' }}</span>
          </div>
          <p v-if="item.errorMessage" class="ops-row-error">
            {{ item.errorCode ?? 'ERROR' }} · {{ item.errorMessage }}
          </p>
          <button
            class="ops-button ops-button-primary"
            type="button"
            :disabled="!item.canRetry || retryMutation.isPending.value"
            @click="retryMutation.mutate(item.id)"
          >
            Retry
          </button>
        </article>
      </div>
    </section>
  </section>
</template>

<style scoped>
.ops-card,
.ops-panel,
.ops-table {
  border-radius: var(--radius-panel);
}

.ops-card {
  display: grid;
  min-height: 116px;
  align-content: space-between;
  padding: 18px;
}

.ops-card span,
.ops-kicker,
.ops-queue-list span,
.ops-metrics-grid span,
.ops-row-meta,
.ops-row-main small {
  color: var(--color-muted);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.ops-card strong {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 2.2rem;
  line-height: 1;
}

.ops-card[data-tone="failed"] strong {
  color: var(--color-signal);
}

.ops-card[data-tone="processing"] strong,
.ops-card[data-tone="queue"] strong {
  color: var(--color-blue);
}

.ops-panel {
  padding: 18px;
}

.ops-panel-compact {
  align-self: start;
}

.ops-panel-head,
.ops-table-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.ops-panel h2,
.ops-table h2 {
  margin: 4px 0 0;
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 1.35rem;
}

.ops-metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.ops-metrics-grid div,
.ops-queue-list div {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 250, 241, 0.5);
  padding: 12px;
}

.ops-metrics-grid strong,
.ops-queue-list strong {
  display: block;
  margin-top: 6px;
  color: var(--color-ink);
  font-size: 1.1rem;
}

.ops-queue-list {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.ops-queue-list-inline {
  grid-template-columns: repeat(2, minmax(92px, 1fr));
  margin-top: 0;
  min-width: 220px;
}

.ops-bars {
  display: grid;
  gap: 14px;
  margin-top: 20px;
}

.ops-bar-row {
  display: grid;
  gap: 7px;
}

.ops-bar-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.ops-bar-meta span {
  color: var(--color-muted);
  font-size: 0.74rem;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.ops-bar-meta strong {
  color: var(--color-ink);
  font-size: 0.86rem;
  font-weight: 900;
}

.ops-bar-track {
  height: 16px;
  overflow: hidden;
  border: 1px solid rgba(82, 111, 122, 0.22);
  border-radius: 999px;
  background:
    linear-gradient(90deg, rgba(82, 111, 122, 0.08), rgba(255, 250, 241, 0.68)),
    rgba(255, 250, 241, 0.9);
  box-shadow: inset 0 1px 2px rgba(33, 43, 41, 0.08);
}

.ops-bar-fill {
  width: 100%;
  height: 100%;
  border-radius: inherit;
  background: var(--color-blue);
  transform: scaleX(var(--bar-scale, 0));
  transform-origin: left center;
  transition: transform 240ms ease;
  box-shadow: inset 0 -1px 0 rgba(255, 255, 255, 0.28);
}

.ops-bar-row[data-tone="active"] .ops-bar-fill {
  background: linear-gradient(90deg, var(--color-blue), #6f8c98);
}

.ops-bar-row[data-tone="waiting"] .ops-bar-fill {
  background: linear-gradient(90deg, var(--color-brass), #d0aa72);
}

.ops-bar-row[data-tone="delayed"] .ops-bar-fill {
  background: linear-gradient(90deg, var(--color-muted), #8c9996);
}

.ops-bar-row[data-tone="failed"] .ops-bar-fill {
  background: linear-gradient(90deg, var(--color-signal), #d07957);
}

.ops-bar-row[data-tone="completed"] .ops-bar-fill {
  background: linear-gradient(90deg, var(--color-blue), #2f5663);
}

.ops-table {
  overflow: hidden;
}

.ops-table-head {
  border-bottom: 1px solid var(--line);
  padding: 18px;
}

.ops-table-head > span {
  color: var(--color-muted);
  font-size: 0.82rem;
  font-weight: 900;
}

.ops-empty,
.ops-error {
  padding: 28px 18px;
  color: var(--color-muted);
  font-weight: 800;
}

.ops-error,
.ops-row-error {
  color: var(--color-signal);
}

.ops-rows {
  display: grid;
}

.ops-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px 18px;
  border-bottom: 1px solid var(--line);
  padding: 16px 18px;
}

.ops-row:last-child {
  border-bottom: 0;
}

.ops-row-main {
  min-width: 0;
}

.ops-file {
  display: block;
  margin-top: 8px;
  overflow-wrap: anywhere;
  color: var(--color-ink);
  font-weight: 900;
}

.ops-row-main small {
  display: block;
  margin-top: 6px;
}

.ops-row-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ops-row-error {
  grid-column: 1 / -1;
  margin: 0;
  overflow-wrap: anywhere;
  font-size: 0.84rem;
  font-weight: 800;
}

.ops-status {
  display: inline-flex;
  border-radius: 999px;
  background: rgba(82, 111, 122, 0.14);
  padding: 5px 9px;
  color: var(--color-blue);
  font-size: 0.7rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.ops-status[data-status="FAILED"],
.ops-status[data-status="DEAD_LETTER"] {
  background: rgba(188, 68, 54, 0.14);
  color: var(--color-signal);
}

.ops-button {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 250, 241, 0.7);
  color: var(--color-ink);
  font-size: 0.8rem;
  font-weight: 900;
  padding: 9px 12px;
  transition: border-color 160ms ease, background 160ms ease, color 160ms ease;
}

.ops-button:hover:not(:disabled) {
  border-color: var(--color-blue);
  background: white;
}

.ops-button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.ops-button-primary {
  align-self: start;
  background: var(--color-blue);
  color: white;
}

@media (max-width: 760px) {
  .ops-metrics-grid {
    grid-template-columns: 1fr;
  }

  .ops-panel-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .ops-queue-list-inline {
    width: 100%;
  }

  .ops-row {
    grid-template-columns: 1fr;
  }
}
</style>
