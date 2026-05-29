<script setup lang="ts">
import anime from 'animejs'
import { onMounted, onUnmounted, useTemplateRef } from 'vue'
import { prefersReducedMotion } from '~/shared/lib/motion'

const rootRef = useTemplateRef<HTMLElement>('ambient')
const animations: anime.AnimeInstance[] = []

function syncAnimationState() {
  const shouldPause = document.hidden
  animations.forEach((animation) => {
    if (shouldPause) {
      animation.pause()
      return
    }

    animation.play()
  })
}

onMounted(() => {
  if (!rootRef.value || prefersReducedMotion()) {
    return
  }

  animations.push(anime({
    targets: rootRef.value,
    '--ambient-shift': ['0px', '42px'],
    '--ambient-glow': [0.82, 1],
    duration: 12000,
    direction: 'alternate',
    easing: 'easeInOutSine',
    loop: true
  }))

  animations.push(anime({
    targets: rootRef.value.querySelectorAll('[data-ribbon]'),
    translateX: (_target: Element, index: number) => index % 2 === 0 ? [0, 54] : [0, -48],
    translateY: (_target: Element, index: number) => index === 1 ? [0, 32] : [0, -24],
    rotate: (_target: Element, index: number) => index === 2 ? [-12, -9] : index === 1 ? [10, 13] : [-8, -11],
    scaleX: [1, 1.05],
    duration: () => anime.random(7200, 9800),
    delay: anime.stagger(520),
    direction: 'alternate',
    easing: 'easeInOutSine',
    loop: true
  }))

  animations.push(anime({
    targets: rootRef.value.querySelectorAll('[data-line]'),
    translateX: [0, 34],
    opacity: [0.26, 0.58],
    duration: 7600,
    delay: anime.stagger(850),
    direction: 'alternate',
    easing: 'easeInOutSine',
    loop: true
  }))

  animations.push(anime({
    targets: rootRef.value.querySelectorAll('[data-trace]'),
    strokeDashoffset: [anime.setDashoffset, 0],
    opacity: [0.1, 0.5],
    duration: 4200,
    delay: anime.stagger(360),
    direction: 'alternate',
    easing: 'easeInOutSine',
    loop: true
  }))

  document.addEventListener('visibilitychange', syncAnimationState)
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', syncAnimationState)
  animations.forEach((animation) => animation.pause())
  animations.length = 0
})
</script>

<template>
  <div ref="ambient" class="ambient-background" aria-hidden="true">
    <div data-ribbon class="ambient-ribbon ambient-ribbon-a" />
    <div data-ribbon class="ambient-ribbon ambient-ribbon-b" />
    <div data-ribbon class="ambient-ribbon ambient-ribbon-c" />
    <div data-line class="ambient-line ambient-line-a" />
    <div data-line class="ambient-line ambient-line-b" />
    <svg class="ambient-traces" viewBox="0 0 1440 920" preserveAspectRatio="none">
      <path data-trace d="M-40 260 C 220 120, 430 420, 690 260 S 1110 110, 1490 290" />
      <path data-trace d="M-80 610 C 210 470, 390 710, 660 560 S 1040 420, 1510 610" />
      <path data-trace d="M140 910 C 340 780, 560 840, 760 720 S 1080 570, 1370 700" />
    </svg>
    <div class="ambient-grain" />
    <div class="ambient-vignette" />
  </div>
</template>

<style scoped>
.ambient-background {
  --ambient-shift: 0px;
  --ambient-glow: 0.82;
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
  background:
    linear-gradient(112deg, rgba(185, 96, 75, 0.22), transparent 31%),
    linear-gradient(246deg, rgba(82, 111, 122, 0.24), transparent 36%),
    linear-gradient(168deg, rgba(184, 146, 93, 0.18), transparent 42%),
    linear-gradient(135deg, #efe3d5 0%, #fbf5e9 42%, #e8f0eb 100%);
  background-position:
    calc(0% + var(--ambient-shift)) 0,
    calc(100% - var(--ambient-shift)) 0,
    50% calc(50% + var(--ambient-shift)),
    0 0;
}

.ambient-background::before {
  position: absolute;
  inset: -20%;
  content: "";
  background:
    linear-gradient(116deg, transparent 0 16%, rgba(255, 255, 255, 0.62) 27%, transparent 43%),
    linear-gradient(24deg, transparent 0 50%, rgba(207, 216, 207, 0.42) 61%, transparent 73%);
  filter: blur(10px);
  opacity: 0.78;
}

.ambient-ribbon {
  position: absolute;
  height: 34vh;
  min-height: 260px;
  max-height: 420px;
  clip-path: polygon(0 34%, 18% 13%, 46% 28%, 71% 7%, 100% 25%, 100% 63%, 73% 81%, 45% 65%, 17% 86%, 0 70%);
  filter: blur(14px);
  opacity: var(--ambient-glow);
  transform: translateZ(0);
  will-change: transform, opacity;
}

.ambient-ribbon-a {
  top: 10%;
  left: -13%;
  width: 76vw;
  rotate: -8deg;
  background: linear-gradient(90deg, transparent 0%, rgba(185, 96, 75, 0.42) 34%, rgba(255, 255, 255, 0.2) 58%, transparent 100%);
}

.ambient-ribbon-b {
  top: 24%;
  right: -22%;
  width: 82vw;
  rotate: 10deg;
  background: linear-gradient(90deg, transparent 0%, rgba(82, 111, 122, 0.36) 30%, rgba(135, 166, 148, 0.3) 66%, transparent 100%);
}

.ambient-ribbon-c {
  right: 10%;
  bottom: -7%;
  width: 70vw;
  rotate: -12deg;
  background: linear-gradient(90deg, transparent 0%, rgba(184, 146, 93, 0.32) 32%, rgba(111, 89, 101, 0.22) 68%, transparent 100%);
}

.ambient-line {
  position: absolute;
  height: 1px;
  border-radius: 999px;
  background: linear-gradient(90deg, transparent, rgba(33, 40, 38, 0.28), transparent);
}

.ambient-line-a {
  top: 34%;
  left: 6%;
  width: 72vw;
  rotate: -5deg;
}

.ambient-line-b {
  right: 0;
  bottom: 24%;
  width: 54vw;
  rotate: 9deg;
}

.ambient-traces {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.ambient-traces path {
  fill: none;
  stroke: rgba(82, 111, 122, 0.34);
  stroke-linecap: round;
  stroke-width: 1.2;
  vector-effect: non-scaling-stroke;
}

.ambient-traces path:nth-child(2) {
  stroke: rgba(185, 96, 75, 0.28);
}

.ambient-traces path:nth-child(3) {
  stroke: rgba(184, 146, 93, 0.3);
}

.ambient-grain {
  position: absolute;
  inset: 0;
  opacity: 0.22;
  background-image:
    repeating-linear-gradient(0deg, rgba(33, 40, 38, 0.045) 0 1px, transparent 1px 5px),
    repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.32) 0 1px, transparent 1px 7px);
  mix-blend-mode: multiply;
}

.ambient-vignette {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(247, 241, 232, 0.18), rgba(247, 241, 232, 0.46)),
    radial-gradient(circle at 55% 42%, transparent 26%, rgba(247, 241, 232, 0.38));
}

@media (max-width: 760px) {
  .ambient-ribbon {
    filter: blur(10px);
    opacity: calc(var(--ambient-glow) * 0.78);
  }

  .ambient-grain {
    opacity: 0.14;
  }

  .ambient-background::before {
    filter: blur(6px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .ambient-ribbon,
  .ambient-line,
  .ambient-traces path {
    transform: none !important;
    stroke-dashoffset: 0 !important;
  }
}
</style>
