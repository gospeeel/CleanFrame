import anime from 'animejs'

export const smoothMotion = {
  easing: 'cubicBezier(0.22, 0.9, 0.22, 1)',
  enterDuration: 860,
  itemDuration: 720,
  microDuration: 520,
  stagger: 95,
  shortLift: 10,
  mediumLift: 16,
  largeLift: 22
}

export function prefersReducedMotion() {
  return process.client && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function createSmoothTimeline() {
  return anime.timeline({
    easing: smoothMotion.easing
  })
}
