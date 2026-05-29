<script setup lang="ts">
interface ActionLink {
  label: string
  to: string
  tone?: 'primary' | 'secondary'
}

defineProps<{
  eyebrow: string
  title: string
  message: string
  code?: string
  actions?: ActionLink[]
}>()
</script>

<template>
  <section class="system-state page-shell">
    <div class="system-card glass-panel">
      <div class="system-copy">
        <p class="system-eyebrow">{{ eyebrow }}</p>
        <h1 class="system-title font-display">{{ title }}</h1>
        <p class="system-message">{{ message }}</p>
        <div v-if="actions?.length" class="system-actions">
          <NuxtLink
            v-for="action in actions"
            :key="`${action.to}-${action.label}`"
            class="system-action"
            :class="{ 'system-action-secondary': action.tone === 'secondary' }"
            :to="action.to"
          >
            {{ action.label }}
          </NuxtLink>
        </div>
      </div>

      <div v-if="code" class="system-code" aria-hidden="true">
        <span>{{ code }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.system-state {
  display: grid;
  min-height: min(680px, calc(100vh - 73px));
  place-items: center;
}

.system-card {
  display: grid;
  width: min(100%, 980px);
  grid-template-columns: minmax(0, 1fr) minmax(180px, 0.36fr);
  gap: clamp(24px, 4vw, 56px);
  overflow: hidden;
  padding: clamp(28px, 5vw, 64px);
}

.system-copy {
  min-width: 0;
}

.system-eyebrow {
  margin: 0;
  color: var(--color-blue);
  font-size: 0.78rem;
  font-weight: 900;
  letter-spacing: 0.26em;
  text-transform: uppercase;
}

.system-title {
  margin: 14px 0 0;
  color: var(--color-ink);
  font-size: clamp(3rem, 7vw, 6rem);
  line-height: 0.92;
}

.system-message {
  max-width: 620px;
  margin: 24px 0 0;
  color: var(--color-muted);
  font-size: clamp(1rem, 1.5vw, 1.16rem);
  font-weight: 800;
  line-height: 1.75;
}

.system-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 30px;
}

.system-action {
  display: inline-flex;
  min-height: 46px;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(47, 86, 99, 0.18);
  border-radius: 12px;
  background: linear-gradient(135deg, var(--color-blue), #2f5663);
  box-shadow: 0 16px 30px rgba(47, 86, 99, 0.22);
  color: white;
  font-size: 0.82rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  padding: 0 18px;
  text-transform: uppercase;
  transition: filter 160ms ease, transform 160ms ease;
}

.system-action:hover {
  filter: brightness(1.05);
  transform: translateY(-1px);
}

.system-action-secondary {
  background: rgba(255, 250, 241, 0.72);
  box-shadow: none;
  color: var(--color-ink);
}

.system-code {
  display: grid;
  min-height: 220px;
  place-items: center;
  border: 1px solid rgba(82, 111, 122, 0.14);
  border-radius: 18px;
  background:
    linear-gradient(135deg, rgba(82, 111, 122, 0.14), transparent 48%),
    rgba(255, 250, 241, 0.44);
}

.system-code span {
  color: rgba(33, 40, 38, 0.15);
  font-family: var(--font-display);
  font-size: clamp(4rem, 12vw, 8rem);
  font-weight: 700;
  line-height: 1;
}

@media (max-width: 760px) {
  .system-card {
    grid-template-columns: 1fr;
  }

  .system-code {
    min-height: 120px;
  }
}
</style>
