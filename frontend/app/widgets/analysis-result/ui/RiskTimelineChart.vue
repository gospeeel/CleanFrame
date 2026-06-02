<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, shallowRef, useTemplateRef, watch } from 'vue'
import type { PresentedScene } from '~/entities/analysis'

const props = defineProps<{
  items: Array<PresentedScene & { originalIndex: number }>
}>()

const emit = defineEmits<{
  selectScene: [index: number]
}>()

const canvasRef = useTemplateRef<HTMLCanvasElement>('canvas')
const chartRef = shallowRef<any>(null)
const chartCtor = shallowRef<any>(null)
const chartError = shallowRef('')

const points = computed(() =>
  props.items.map((item, index) => ({
    x: item.scene.timeline_position ?? item.scene.element_index ?? index + 1,
    y: item.scene.уровень ?? 0,
    sceneIndex: item.originalIndex,
    label: item.categoryLabel,
    rating: item.scene.рейтинг,
    text: item.scene.текст_сцены
  }))
)

const sortedPoints = computed(() =>
  [...points.value].sort((a, b) => a.x - b.x)
)

const trendPoints = computed(() => {
  const source = sortedPoints.value
  const first = source[0]
  const last = source[source.length - 1]

  if (!first || !last) {
    return []
  }

  const span = Math.max(1, last.x - first.x)

  return [
    { x: Math.max(0, first.x - span * 0.18), y: 0 },
    ...source.map((point) => ({ x: point.x, y: point.y })),
    { x: last.x + span * 0.18, y: 0 }
  ]
})

const xBounds = computed(() => {
  const source = sortedPoints.value
  const first = source[0]
  const last = source[source.length - 1]
  if (!first || !last) {
    return { min: 0, max: 1 }
  }

  const span = Math.max(1, last.x - first.x)
  const padding = Math.max(1, span * 0.04)
  return {
    min: first.x - padding,
    max: last.x + padding
  }
})

async function ensureChart() {
  if (chartCtor.value) {
    return chartCtor.value
  }

  const chartModule = await import('chart.js/auto')
  chartCtor.value = chartModule.default
  return chartModule.default
}

async function renderChart() {
  await nextTick()

  if (!canvasRef.value || !points.value.length) {
    return
  }

  try {
    chartError.value = ''
    const Chart = await ensureChart()
    chartRef.value?.destroy()

    const canvas = canvasRef.value
    const context = canvas.getContext('2d')
    const gradient = context?.createLinearGradient(0, 0, 0, canvas.clientHeight || 300)
    gradient?.addColorStop(0, 'rgba(82, 111, 122, 0.22)')
    gradient?.addColorStop(0.72, 'rgba(82, 111, 122, 0.08)')
    gradient?.addColorStop(1, 'rgba(82, 111, 122, 0)')

    chartRef.value = new Chart(canvas, {
      type: 'line',
      data: {
        datasets: [
          {
            label: 'Кривая риска',
            data: trendPoints.value,
            borderColor: 'rgba(82, 111, 122, 0.86)',
            backgroundColor: gradient ?? 'rgba(82, 111, 122, 0.14)',
            borderWidth: 3,
            fill: true,
            pointRadius: 0,
            pointHitRadius: 0,
            tension: 0.36,
            cubicInterpolationMode: 'monotone',
            order: 2
          },
          {
            label: 'Сцены',
            data: sortedPoints.value,
            borderColor: sortedPoints.value.map((point) => colorFor(point.label)),
            backgroundColor: sortedPoints.value.map((point) => colorFor(point.label)),
            pointRadius: 6,
            pointHoverRadius: 9,
            pointBorderWidth: 2,
            pointBorderColor: '#fffaf1',
            showLine: false,
            type: 'scatter',
            order: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        parsing: false,
        interaction: {
          mode: 'nearest',
          intersect: true
        },
        layout: {
          padding: {
            top: 18,
            right: 22,
            bottom: 8,
            left: 8
          }
        },
        scales: {
          x: {
            type: 'linear',
            min: xBounds.value.min,
            max: xBounds.value.max,
            grid: {
              color: 'rgba(50, 58, 54, 0.08)'
            },
            border: {
              color: 'rgba(50, 58, 54, 0.14)'
            },
            title: {
              display: true,
              text: 'Позиция в сценарии',
              color: '#6d7771',
              font: { size: 12, weight: 700 }
            },
            ticks: {
              precision: 0,
              color: '#6d7771',
              font: { size: 11, weight: 700 }
            }
          },
          y: {
            min: -0.15,
            max: 4.25,
            grid: {
              color: 'rgba(50, 58, 54, 0.1)'
            },
            border: {
              color: 'rgba(50, 58, 54, 0.14)'
            },
            title: {
              display: true,
              text: 'Уровень риска',
              color: '#6d7771',
              font: { size: 12, weight: 700 }
            },
            ticks: {
              stepSize: 1,
              color: '#6d7771',
              font: { size: 11, weight: 700 },
              callback: (value: string | number) => Number.isInteger(Number(value)) ? value : ''
            }
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            filter: (item: any) => item.datasetIndex === 1,
            enabled: true,
            displayColors: false,
            backgroundColor: 'rgba(255, 250, 241, 0.98)',
            titleColor: '#2f3733',
            bodyColor: '#66736c',
            borderColor: 'rgba(50, 58, 54, 0.16)',
            borderWidth: 1,
            cornerRadius: 12,
            padding: 14,
            caretSize: 7,
            caretPadding: 8,
            boxPadding: 6,
            titleFont: {
              size: 13,
              weight: 800
            },
            bodyFont: {
              size: 12,
              weight: 700,
              lineHeight: 1.45
            },
            titleMarginBottom: 8,
            bodySpacing: 4,
            callbacks: {
              title: (items: any[]) => {
                const point = items[0]?.raw
                return point ? `${point.label} · ${point.rating}` : ''
              },
              label: (item: any) => {
                const point = item.raw
                if (!point?.text) {
                  return ''
                }

                return wrapTooltipText(point.text, 72)
              }
            }
          }
        },
        onClick: (_event: unknown, elements: any[]) => {
          const element = elements.find((candidate) => candidate.datasetIndex === 1)
          if (!element) {
            return
          }

          const point = sortedPoints.value[element.index]
          if (point) {
            emit('selectScene', point.sceneIndex)
          }
        }
      }
    })
  } catch (error) {
    chartError.value = error instanceof Error ? error.message : 'Не удалось построить график'
  }
}

function colorFor(label: string) {
  if (label.includes('Насилие')) return '#b9604b'
  if (label.includes('лексика')) return '#6f5965'
  if (label.includes('Алкоголь')) return '#b8925d'
  if (label.includes('Интим')) return '#b9608f'
  if (label.includes('Пуга')) return '#526f7a'
  return '#87a694'
}

function wrapTooltipText(text: string, lineLength: number) {
  const words = text.split(/\s+/)
  const lines: string[] = []
  let line = ''

  for (const word of words) {
    const nextLine = line ? `${line} ${word}` : word
    if (nextLine.length > lineLength && line) {
      lines.push(line)
      line = word
    } else {
      line = nextLine
    }
  }

  if (line) {
    lines.push(line)
  }

  return lines.slice(0, 4)
}

onMounted(renderChart)
watch(points, renderChart)

onBeforeUnmount(() => {
  chartRef.value?.destroy()
})
</script>

<template>
  <div class="risk-chart border border-line p-4 shadow-soft md:p-5">
    <div class="mb-4 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
      <div>
        <p class="text-xs font-black uppercase tracking-[0.18em] text-steel">пики возрастного риска</p>
        <p class="mt-2 text-xs leading-5 text-muted">Кривая показывает интенсивность риска по сценарию. Точки раскрывают фрагменты.</p>
      </div>
      <p class="text-xs font-black uppercase tracking-[0.14em] text-muted">{{ points.length }} точек</p>
    </div>
    <div class="chart-frame min-w-0">
      <p v-if="chartError" class="chart-error text-sm font-bold text-signal">
        Не удалось построить график риска.
      </p>
      <canvas ref="canvas" />
    </div>
  </div>
</template>

<style scoped>
.risk-chart {
  position: relative;
  z-index: 1;
  overflow: hidden;
  border-radius: var(--radius-control);
  background:
    linear-gradient(180deg, rgba(255, 250, 241, 0.96), rgba(248, 242, 232, 0.9)),
    linear-gradient(120deg, rgba(82, 111, 122, 0.08), transparent 42%);
}

.chart-frame {
  position: relative;
  height: 240px;
  border-radius: 14px;
  background: rgba(255, 250, 241, 0.68);
}

.chart-frame canvas {
  display: block;
  height: 100% !important;
  width: 100% !important;
}

.chart-error {
  position: absolute;
  left: 16px;
  top: 16px;
  z-index: 1;
}

@media (min-width: 768px) {
  .chart-frame {
    height: 300px;
  }
}
</style>
