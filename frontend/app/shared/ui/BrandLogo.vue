<script setup lang="ts">
import anime from 'animejs'
import { computed, onMounted, onUnmounted, useTemplateRef } from 'vue'
import { createSmoothTimeline, prefersReducedMotion, smoothMotion } from '~/shared/lib/motion'

const props = withDefaults(defineProps<{
  showText?: boolean
  showTagline?: boolean
  size?: 'sm' | 'md' | 'lg'
  animated?: boolean
}>(), {
  showText: true,
  showTagline: true,
  size: 'md',
  animated: true
})

const rootRef = useTemplateRef<HTMLElement>('root')

const rootClass = computed(() => [
  'brand-logo',
  `brand-logo--${props.size}`,
  {
    'brand-logo--text': props.showText,
    'brand-logo--mark-only': !props.showText,
    'brand-logo--animated': props.animated
  }
])

let logoTimeline: anime.AnimeTimelineInstance | null = null
let idleAnimation: anime.AnimeInstance | null = null
let focusIdleAnimation: anime.AnimeInstance | null = null

onMounted(() => {
  const root = rootRef.value
  if (!root || !props.animated || prefersReducedMotion()) {
    return
  }

  logoTimeline = createSmoothTimeline()
    .add({
      targets: root.querySelectorAll('[data-logo-corner]'),
      strokeDashoffset: [anime.setDashoffset, 0],
      opacity: [0, 1],
      delay: anime.stagger(120),
      duration: 760
    })
    .add({
      targets: root.querySelector('[data-logo-orb]'),
      scale: [0.42, 1.04, 1],
      opacity: [0, 0.78, 0.92],
      duration: 940
    }, '-=220')
    .add({
      targets: root.querySelector('[data-logo-accent]'),
      translateX: [10, 0],
      translateY: [-10, 0],
      scale: [0.24, 1],
      opacity: [0, 1],
      duration: 620
    }, '-=360')
    .add({
      targets: root.querySelector('[data-logo-focus]'),
      translateX: ['-86%', '86%'],
      rotate: [-18, -18],
      opacity: [0, 0.72, 0],
      duration: 980
    }, '-=180')
    .add({
      targets: root.querySelector('[data-logo-orb]'),
      scale: [1.02, 1],
      opacity: [0.96, 0.9],
      duration: smoothMotion.microDuration
    }, '-=260')
    .add({
      targets: root.querySelectorAll('[data-logo-word]'),
      translateY: [8, 0],
      opacity: [0, 1],
      delay: anime.stagger(90),
      duration: 680
    }, '-=420')

  logoTimeline.finished.then(() => {
    if (!rootRef.value || prefersReducedMotion()) {
      return
    }

    idleAnimation = anime({
      targets: [
        root.querySelector('[data-logo-orb]'),
        root.querySelector('[data-logo-accent]')
      ],
      scale: [
        { value: 1.045, duration: 1400 },
        { value: 1, duration: 1200 }
      ],
      opacity: [
        { value: 1, duration: 900 },
        { value: 0.9, duration: 1100 }
      ],
      delay: anime.stagger(220),
      endDelay: 2600,
      easing: 'easeInOutSine',
      loop: true
    })

    focusIdleAnimation = anime({
      targets: root.querySelector('[data-logo-focus]'),
      translateX: ['-86%', '86%'],
      opacity: [0, 0.58, 0],
      duration: 1400,
      easing: 'easeInOutSine',
      delay: 1800,
      endDelay: 4200,
      loop: true
    })
  }).catch(() => undefined)
})

onUnmounted(() => {
  logoTimeline?.pause()
  idleAnimation?.pause()
  focusIdleAnimation?.pause()
  logoTimeline = null
  idleAnimation = null
  focusIdleAnimation = null
})
</script>

<template>
  <span ref="root" :class="rootClass" aria-label="Чистый Кадр">
    <span class="brand-logo__mark" aria-hidden="true">
      <span data-logo-orb class="brand-logo__orb" />
      <span data-logo-focus class="brand-logo__focus" />
      <span data-logo-accent class="brand-logo__accent" />
      <svg class="brand-logo__frame" viewBox="0 0 96 96" fill="none">
        <path data-logo-corner class="brand-logo__corner" d="M30 14H15C13.9 14 13 14.9 13 16V33" />
        <path data-logo-corner class="brand-logo__corner brand-logo__corner--top-gap" d="M55 14H67" />
        <path data-logo-corner class="brand-logo__corner" d="M82 23V34" />
        <path data-logo-corner class="brand-logo__corner" d="M30 82H15C13.9 82 13 81.1 13 80V63" />
        <path data-logo-corner class="brand-logo__corner" d="M66 82H81C82.1 82 83 81.1 83 80V63" />
      </svg>
    </span>

    <span v-if="showText" class="brand-logo__copy">
      <span data-logo-word class="brand-logo__name font-display">Чистый Кадр</span>
      <span v-if="showTagline" data-logo-word class="brand-logo__tagline">
        анализ сценариев на риски с помощью ИИ
      </span>
    </span>
  </span>
</template>

<style scoped>
.brand-logo {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  color: var(--color-ink);
}

.brand-logo--text {
  gap: 14px;
}

.brand-logo--mark-only {
  width: var(--brand-mark-size);
  height: var(--brand-mark-size);
}

.brand-logo--sm {
  --brand-mark-size: 46px;
  --brand-name-size: 22px;
  --brand-tagline-size: 11px;
}

.brand-logo--md {
  --brand-mark-size: 60px;
  --brand-name-size: 32px;
  --brand-tagline-size: 13px;
}

.brand-logo--lg {
  --brand-mark-size: 78px;
  --brand-name-size: 44px;
  --brand-tagline-size: 15px;
}

.brand-logo__mark {
  position: relative;
  display: grid;
  flex: 0 0 auto;
  width: var(--brand-mark-size);
  height: var(--brand-mark-size);
  place-items: center;
}

.brand-logo__orb {
  position: absolute;
  width: 56%;
  height: 56%;
  border-radius: 999px;
  background:
    radial-gradient(circle at 48% 42%, rgba(255, 250, 241, 0.74), rgba(226, 222, 209, 0.48) 34%, rgba(133, 143, 138, 0.18) 68%, rgba(133, 143, 138, 0.04) 100%);
  filter: blur(0.8px);
  box-shadow:
    0 18px 38px rgba(82, 111, 122, 0.08),
    inset 12px 10px 26px rgba(255, 255, 255, 0.62),
    inset -14px -12px 28px rgba(82, 111, 122, 0.08);
}

.brand-logo__focus {
  position: absolute;
  width: 48%;
  height: 120%;
  border-radius: 999px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.74), transparent);
  mix-blend-mode: screen;
  opacity: 0;
}

.brand-logo__accent {
  position: absolute;
  top: 7%;
  right: 8%;
  width: 13%;
  height: 13%;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--color-coral), #f07656);
  box-shadow: 0 7px 16px rgba(185, 96, 75, 0.22);
}

.brand-logo__frame {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.brand-logo__corner {
  stroke: var(--color-blue);
  stroke-width: 3.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.brand-logo__corner--top-gap {
  stroke-width: 3.2;
}

.brand-logo__copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  line-height: 1;
}

.brand-logo__name {
  display: block;
  color: var(--color-ink);
  font-size: var(--brand-name-size);
  font-weight: 600;
  letter-spacing: 0;
  white-space: nowrap;
}

.brand-logo__tagline {
  display: block;
  margin-top: 7px;
  color: var(--color-muted);
  font-size: var(--brand-tagline-size);
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
}

.brand-logo--animated .brand-logo__corner,
.brand-logo--animated .brand-logo__orb,
.brand-logo--animated .brand-logo__accent,
.brand-logo--animated .brand-logo__name,
.brand-logo--animated .brand-logo__tagline {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .brand-logo--animated .brand-logo__corner,
  .brand-logo--animated .brand-logo__orb,
  .brand-logo--animated .brand-logo__accent,
  .brand-logo--animated .brand-logo__name,
  .brand-logo--animated .brand-logo__tagline {
    opacity: 1;
  }
}
</style>
