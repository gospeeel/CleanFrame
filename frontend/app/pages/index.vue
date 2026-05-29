<script setup lang="ts">
import anime from 'animejs'
import { computed, onMounted, useTemplateRef } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '~/entities/user'
import { createSmoothTimeline, prefersReducedMotion, smoothMotion } from '~/shared/lib/motion'

const auth = useAuthStore()
const { user } = storeToRefs(auth)
const rootRef = useTemplateRef<HTMLElement>('root')

const greeting = computed(() => user.value?.login ? `Добро пожаловать, ${user.value.login}` : 'Добро пожаловать')

const metrics = [
  { label: 'Форматы', value: 'DOCX/PDF', tone: 'bg-signal', accent: 'metric-card-signal' },
  { label: 'Контур', value: 'NLP + RuBERT', tone: 'bg-denim', accent: 'metric-card-denim' },
  { label: 'Результат', value: 'рейтинг + правки', tone: 'bg-brass', accent: 'metric-card-brass' }
]

onMounted(() => {
  if (!rootRef.value || prefersReducedMotion()) {
    return
  }

  createSmoothTimeline()
    .add({
      targets: rootRef.value.querySelector('[data-hero]'),
      translateY: [smoothMotion.largeLift, 0],
      opacity: [0, 1],
      duration: smoothMotion.enterDuration
    })
    .add({
      targets: rootRef.value.querySelectorAll('[data-card]'),
      translateY: [smoothMotion.mediumLift, 0],
      opacity: [0, 1],
      delay: anime.stagger(smoothMotion.stagger),
      duration: smoothMotion.itemDuration
    }, '-=520')
    .add({
      targets: rootRef.value.querySelectorAll('[data-track]'),
      scaleX: [0, 1],
      opacity: [0, 1],
      delay: anime.stagger(115),
      duration: smoothMotion.itemDuration
    }, '-=600')
})
</script>

<template>
  <section ref="root" class="page-shell">
    <div data-hero class="dashboard-hero glass-panel overflow-hidden opacity-0">
      <div class="grid min-h-[480px] lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.75fr)]">
        <div class="flex flex-col justify-between panel-pad">
          <div>
            <p class="text-xs font-black uppercase tracking-[0.24em] text-steel">{{ greeting }}</p>
            <h1 class="page-title mt-5 max-w-4xl font-display font-semibold text-ink">
              Светлый пульт анализа сценариев
            </h1>
            <p class="mt-5 max-w-2xl text-base leading-7 text-muted">
              Единый рабочий экран для загрузки текста, оценки возрастных рисков и подготовки редакционных рекомендаций.
            </p>
          </div>

          <div class="mt-8 flex flex-col gap-3 sm:flex-row">
            <NuxtLink
              class="inline-flex justify-center rounded-[var(--radius-control)] bg-steel px-5 py-4 text-sm font-black uppercase tracking-[0.14em] text-paper shadow-soft transition hover:-translate-y-0.5 hover:bg-signal"
              to="/report"
            >
              Начать анализ
            </NuxtLink>
            <NuxtLink
              class="inline-flex justify-center rounded-[var(--radius-control)] border border-line bg-milk/70 px-5 py-4 text-sm font-black uppercase tracking-[0.14em] text-ink transition hover:border-steel hover:bg-white"
              to="/history"
            >
              Открыть историю
            </NuxtLink>
          </div>
        </div>

        <div class="hero-side relative border-t border-line panel-pad lg:border-l lg:border-t-0">
          <div class="absolute inset-x-6 top-8 h-px bg-gradient-to-r from-transparent via-steel/35 to-transparent" />
          <div class="grid h-full content-end gap-4 pt-8">
            <div
              v-for="(metric, index) in metrics"
              :key="metric.label"
              data-card
              class="metric-card border border-line p-5 opacity-0 shadow-soft"
              :class="metric.accent"
            >
              <div class="flex items-center justify-between gap-4">
                <p class="text-xs font-black uppercase tracking-[0.24em] text-muted">{{ metric.label }}</p>
                <span class="h-1.5 w-10 rounded-full" :class="metric.tone" />
              </div>
              <p class="mt-5 break-words font-display text-2xl font-semibold text-ink md:text-3xl">{{ metric.value }}</p>
              <div
                data-track
                class="mt-5 h-1 origin-left rounded-full opacity-0"
                :class="metric.tone"
                :style="{ width: `${95 - index * 18}%` }"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.dashboard-hero {
  position: relative;
  border-radius: var(--radius-panel);
}

.dashboard-hero::before {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(145deg, rgba(184, 146, 93, 0.12), transparent 35%),
    linear-gradient(320deg, rgba(82, 111, 122, 0.13), transparent 42%);
  content: "";
  pointer-events: none;
}

.dashboard-hero > * {
  position: relative;
}

.hero-side {
  background:
    linear-gradient(160deg, rgba(255, 250, 241, 0.72), rgba(232, 240, 235, 0.52)),
    linear-gradient(42deg, transparent, rgba(184, 146, 93, 0.14));
}

.metric-card {
  border-radius: 18px;
  background: rgba(255, 250, 241, 0.72);
}

.metric-card-signal {
  box-shadow: 0 16px 44px rgba(185, 96, 75, 0.12);
}

.metric-card-denim {
  box-shadow: 0 16px 44px rgba(82, 111, 122, 0.13);
}

.metric-card-brass {
  box-shadow: 0 16px 44px rgba(184, 146, 93, 0.13);
}
</style>
