<script setup lang="ts">
import anime from 'animejs'
import { computed, onMounted, useTemplateRef } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '~/entities/user'
import { createSmoothTimeline, prefersReducedMotion, smoothMotion } from '~/shared/lib/motion'
import BrandLogo from '~/shared/ui/BrandLogo.vue'
import NotificationCenter from './NotificationCenter.vue'

const auth = useAuthStore()
const { user, isRestored, isRestoring } = storeToRefs(auth)
const router = useRouter()
const route = useRoute()
const headerRef = useTemplateRef<HTMLElement>('header')

const isStandalonePage = computed(() =>
  route.path === '/login' ||
  route.path === '/register' ||
  route.path === '/unauthorized' ||
  route.path === '/forbidden' ||
  route.path === '/not-found' ||
  route.name === 'slug'
)
const isAuthStateReady = computed(() => isRestored.value && !isRestoring.value)
const isAdmin = computed(() => user.value?.role === 'ADMIN' || user.value?.role === 'SUPER_ADMIN')
const mobileNavClass = computed(() => isAdmin.value ? 'grid-cols-4' : 'grid-cols-3')
const initials = computed(() => user.value?.login?.slice(0, 2).toUpperCase() ?? '...')
const displayLogin = computed(() => {
  if (user.value?.login) {
    return user.value.login
  }

  return isAuthStateReady.value ? 'Не авторизован' : 'Проверяем сессию'
})
const roleLabel = computed(() => {
  if (user.value?.role === 'SUPER_ADMIN') return 'Главный администратор'
  if (user.value?.role === 'ADMIN') return 'Администратор'
  if (user.value) return 'Пользователь'
  return isAuthStateReady.value ? 'Гость' : 'Загрузка'
})

async function logout() {
  await auth.logout()
  router.replace('/login')
}

onMounted(() => {
  if (!headerRef.value || prefersReducedMotion()) {
    return
  }

  createSmoothTimeline()
    .add({
      targets: headerRef.value,
      translateY: [-smoothMotion.shortLift, 0],
      opacity: [0.86, 1],
      duration: smoothMotion.enterDuration
    })
    .add({
      targets: headerRef.value.querySelectorAll('[data-nav-item]'),
      translateY: [-6, 0],
      opacity: [0.72, 1],
      delay: anime.stagger(85),
      duration: smoothMotion.microDuration
    }, '-=560')
})
</script>

<template>
  <header
    ref="header"
    class="sticky top-0 z-30 border-b border-line bg-paper/72 backdrop-blur-xl"
  >
    <div class="mx-auto flex max-w-[1440px] items-center justify-between gap-4 px-4 py-3 md:px-8">
      <NuxtLink class="group flex min-w-0 items-center gap-3" to="/">
        <BrandLogo size="md" class="transition group-hover:-translate-y-0.5" />
      </NuxtLink>

      <nav
        v-if="!isStandalonePage"
        class="hidden items-center rounded-[14px] border border-line bg-milk/38 p-1 shadow-soft backdrop-blur md:flex"
      >
        <NuxtLink
          data-nav-item
          class="rounded-[10px] px-4 py-2 text-sm font-bold text-muted transition hover:bg-steel hover:text-paper"
          active-class="bg-steel text-paper"
          to="/report"
        >
          Анализ
        </NuxtLink>
        <NuxtLink
          data-nav-item
          class="rounded-[10px] px-4 py-2 text-sm font-bold text-muted transition hover:bg-steel hover:text-paper"
          active-class="bg-steel text-paper"
          to="/history"
        >
          История
        </NuxtLink>
        <NuxtLink
          data-nav-item
          class="rounded-[10px] px-4 py-2 text-sm font-bold text-muted transition hover:bg-steel hover:text-paper"
          active-class="bg-steel text-paper"
          to="/compare"
        >
          Сравнение
        </NuxtLink>
        <NuxtLink
          v-if="isAdmin"
          data-nav-item
          class="rounded-[10px] px-4 py-2 text-sm font-bold text-muted transition hover:bg-steel hover:text-paper"
          active-class="bg-steel text-paper"
          to="/ops"
        >
          Ops
        </NuxtLink>
      </nav>

      <div v-if="!isStandalonePage" class="flex min-w-0 items-center gap-2 sm:gap-3">
        <NotificationCenter v-if="user" />
        <div class="hidden text-right sm:block">
          <p class="text-sm font-bold text-ink">{{ displayLogin }}</p>
          <p class="text-xs uppercase tracking-[0.16em] text-muted">{{ roleLabel }}</p>
        </div>
        <NuxtLink
          class="grid h-10 w-10 overflow-hidden place-items-center rounded-[12px] border border-line bg-milk text-xs font-black text-steel transition hover:border-steel hover:bg-white"
          to="/profile"
        >
          <img v-if="user?.avatarUrl" :src="user.avatarUrl" alt="" class="h-full w-full object-cover">
          <span v-else>{{ initials }}</span>
        </NuxtLink>
        <button
          class="rounded border border-line bg-milk/60 px-3 py-2 text-sm font-bold text-muted transition hover:border-signal hover:bg-signal hover:text-white max-sm:hidden"
          type="button"
          @click="logout"
        >
          Выйти
        </button>
      </div>
    </div>

    <nav
      v-if="!isStandalonePage"
      class="grid border-t border-line bg-paper/82 px-3 py-2 backdrop-blur-xl md:hidden"
      :class="mobileNavClass"
    >
      <NuxtLink
        class="rounded-[10px] px-3 py-2 text-center text-xs font-black uppercase tracking-[0.12em] text-muted"
        active-class="bg-steel text-paper"
        to="/report"
      >
        Анализ
      </NuxtLink>
      <NuxtLink
        class="rounded-[10px] px-3 py-2 text-center text-xs font-black uppercase tracking-[0.12em] text-muted"
        active-class="bg-steel text-paper"
        to="/history"
      >
        История
      </NuxtLink>
      <NuxtLink
        class="rounded-[10px] px-3 py-2 text-center text-xs font-black uppercase tracking-[0.12em] text-muted"
        active-class="bg-steel text-paper"
        to="/compare"
      >
        Сравнение
      </NuxtLink>
      <NuxtLink
        v-if="isAdmin"
        class="rounded-[10px] px-3 py-2 text-center text-xs font-black uppercase tracking-[0.12em] text-muted"
        active-class="bg-steel text-paper"
        to="/ops"
      >
        Ops
      </NuxtLink>
    </nav>
  </header>
</template>
