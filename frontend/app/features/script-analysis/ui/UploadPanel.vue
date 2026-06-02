<script setup lang="ts">
import anime from 'animejs'
import { computed, onMounted, shallowRef, useTemplateRef, watch } from 'vue'
import type { AnalysisTargetRating } from '~/entities/analysis'
import { createSmoothTimeline, prefersReducedMotion, smoothMotion } from '~/shared/lib/motion'

const selectedFileName = defineModel<string>('selectedFileName', { default: '' })

const emit = defineEmits<{
  submit: [file: File, targetRating: AnalysisTargetRating]
}>()

const rootRef = useTemplateRef<HTMLElement>('root')
const fileInputRef = useTemplateRef<HTMLInputElement>('fileInput')
const selectedFile = shallowRef<File | null>(null)
const targetRating = shallowRef<AnalysisTargetRating>('raw')
const isDragOver = shallowRef(false)
const targetOptions: Array<{ value: AnalysisTargetRating; label: string; hint: string }> = [
  { value: 'raw', label: 'Raw', hint: 'Все риски без цели снижения' },
  { value: '6+', label: '6+', hint: 'Самый строгий порог' },
  { value: '12+', label: '12+', hint: 'Массовый семейный прокат' },
  { value: '16+', label: '16+', hint: 'Меньше правок для взрослой драмы' },
  { value: '18+', label: '18+', hint: 'Только критичные превышения' }
]

const canSubmit = computed(() => selectedFile.value !== null)
const fileMeta = computed(() => {
  if (!selectedFile.value) {
    return 'DOCX, PDF или TXT до 50 МБ'
  }

  return `${(selectedFile.value.size / 1024 / 1024).toFixed(2)} МБ`
})

function selectFile() {
  fileInputRef.value?.click()
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null

  setSelectedFile(file)
}

function setSelectedFile(file: File | null) {
  selectedFile.value = file
  selectedFileName.value = file?.name ?? ''
}

function isSupportedFile(file: File) {
  const name = file.name.toLowerCase()
  return name.endsWith('.txt') || name.endsWith('.pdf') || name.endsWith('.docx')
}

function handleDragOver(event: DragEvent) {
  event.preventDefault()
  isDragOver.value = true
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy'
  }
}

function handleDragLeave(event: DragEvent) {
  if (event.currentTarget === event.target) {
    isDragOver.value = false
  }
}

function handleDrop(event: DragEvent) {
  event.preventDefault()
  isDragOver.value = false

  const file = event.dataTransfer?.files?.[0] ?? null
  if (!file || !isSupportedFile(file)) {
    return
  }

  setSelectedFile(file)
}

function submitFile() {
  if (!selectedFile.value) {
    return
  }

  emit('submit', selectedFile.value, targetRating.value)
}

function animateSelectPulse() {
  const target = rootRef.value?.querySelector('[data-file-card]')
  if (!target) {
    return
  }

  anime({
    targets: target,
    scale: [0.992, 1],
    borderColor: ['rgba(82, 111, 122, 0.55)', 'rgba(50, 58, 54, 0.14)'],
    duration: smoothMotion.microDuration,
    easing: smoothMotion.easing
  })
}

onMounted(() => {
  if (!rootRef.value || prefersReducedMotion()) {
    rootRef.value?.querySelectorAll('.opacity-0').forEach((element) => {
      element.classList.remove('opacity-0')
    })
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
      targets: rootRef.value.querySelectorAll('[data-animate]'),
      translateY: [smoothMotion.mediumLift, 0],
      opacity: [0, 1],
      delay: anime.stagger(smoothMotion.stagger),
      duration: smoothMotion.itemDuration
    }, '-=520')
    .add({
      targets: rootRef.value.querySelectorAll('[data-rail]'),
      scaleX: [0, 1],
      opacity: [0, 1],
      delay: anime.stagger(100),
      duration: smoothMotion.itemDuration
    }, '-=620')
})

watch(selectedFile, () => {
  requestAnimationFrame(animateSelectPulse)
})
</script>

<template>
  <section ref="root" class="upload-panel glass-panel overflow-hidden panel-pad">
    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.72fr)]">
      <div>
        <div data-title class="opacity-0">
          <h1 class="section-title mt-3 max-w-3xl font-display font-semibold text-ink">
            Анализ сценария на возрастные ограничения
          </h1>
          <p class="mt-4 max-w-2xl text-base leading-7 text-muted">
            Загрузите сценарий, чтобы система выделила рискованные сцены, рассчитала возрастной рейтинг и предложила редакционные правки.
          </p>
        </div>

        <div class="mt-6 grid gap-3 md:grid-cols-3">
          <div data-animate class="process-card opacity-0">
            <p class="text-2xl font-black text-ink">01</p>
            <p class="mt-2 text-sm font-bold text-muted">Парсинг документа</p>
          </div>
          <div data-animate class="process-card opacity-0">
            <p class="text-2xl font-black text-ink">02</p>
            <p class="mt-2 text-sm font-bold text-muted">NLP-фильтрация</p>
          </div>
          <div data-animate class="process-card opacity-0">
            <p class="text-2xl font-black text-ink">03</p>
            <p class="mt-2 text-sm font-bold text-muted">RuBERT-рейтинг</p>
          </div>
        </div>
      </div>

      <div data-animate class="min-w-0 opacity-0">
        <div data-file-card class="file-card border border-line p-4 shadow-soft transition">
          <div class="mb-4 rounded-[14px] border border-line bg-paper/58 p-3">
            <p class="text-xs font-black uppercase tracking-[0.18em] text-steel">Цель анализа</p>
            <div class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
              <button
                v-for="option in targetOptions"
                :key="option.value"
                class="target-option min-w-0"
                :class="targetRating === option.value ? 'target-option-active' : ''"
                type="button"
                @click="targetRating = option.value"
              >
                <span class="block text-sm font-black">{{ option.label }}</span>
                <span class="mt-1 block text-[11px] font-bold leading-4">{{ option.hint }}</span>
              </button>
            </div>
            <p class="mt-3 text-xs font-bold leading-5 text-muted">
              Выберите порог до отправки файла. Raw показывает все найденные риски без цели снижения.
            </p>
          </div>

          <input
            ref="fileInput"
            class="sr-only"
            type="file"
            accept=".docx,.pdf,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            @change="handleFileChange"
          >

          <button
            class="hairline-grid group flex min-h-48 w-full flex-col justify-between rounded-[18px] border border-dashed border-steel/35 bg-milk/55 p-5 text-left transition hover:border-steel hover:bg-white md:min-h-56"
            :class="isDragOver ? 'border-steel bg-white shadow-soft' : ''"
            type="button"
            @click="selectFile"
            @dragenter.prevent="isDragOver = true"
            @dragover="handleDragOver"
            @dragleave="handleDragLeave"
            @drop="handleDrop"
          >
            <span class="flex items-center justify-between gap-4">
              <span class="rounded-[10px] border border-line bg-paper/80 px-3 py-1 text-xs font-black uppercase tracking-[0.2em] text-muted">
                Загрузка
              </span>
              <span class="text-sm font-bold text-steel transition group-hover:translate-x-1">Выбрать</span>
            </span>
            <span>
              <span class="block max-w-full break-words font-display text-2xl font-semibold leading-tight text-ink md:text-3xl">
                {{ selectedFileName || 'Перетащите или выберите файл сценария' }}
              </span>
              <span class="mt-3 block text-sm font-bold text-muted">{{ fileMeta }}</span>
            </span>
          </button>

          <button
            class="mt-4 inline-flex w-full items-center justify-center rounded-[var(--radius-control)] bg-steel px-5 py-4 text-sm font-black uppercase tracking-[0.14em] text-paper shadow-soft transition hover:-translate-y-0.5 hover:bg-signal disabled:cursor-not-allowed disabled:bg-steel/25 disabled:hover:translate-y-0"
            type="button"
            :disabled="!canSubmit"
            @click="submitFile"
          >
            Запустить анализ
          </button>
        </div>

        <div class="mt-5 space-y-2">
          <div data-rail class="h-1 origin-left rounded-full bg-signal opacity-0" />
          <div data-rail class="h-1 w-2/3 origin-left rounded-full bg-denim opacity-0" />
          <div data-rail class="h-1 w-1/3 origin-left rounded-full bg-brass opacity-0" />
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.upload-panel {
  position: relative;
  border-radius: var(--radius-panel);
}

.upload-panel::before {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(140deg, rgba(82, 111, 122, 0.1), transparent 32%),
    linear-gradient(310deg, rgba(184, 146, 93, 0.12), transparent 38%);
  content: "";
  pointer-events: none;
}

.upload-panel > * {
  position: relative;
}

.process-card,
.file-card {
  border-radius: 18px;
  border: 1px solid var(--line);
  background: rgba(255, 250, 241, 0.68);
}

.process-card {
  padding: 16px;
}

.target-option {
  min-height: 70px;
  border: 1px solid rgba(33, 43, 41, 0.12);
  border-radius: 10px;
  background: rgba(255, 250, 241, 0.7);
  color: var(--color-muted);
  padding: 8px;
  text-align: left;
  transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease, transform 160ms ease;
}

.target-option:hover,
.target-option-active {
  border-color: rgba(82, 111, 122, 0.42);
  background: white;
  color: var(--color-ink);
  transform: translateY(-1px);
}
</style>
