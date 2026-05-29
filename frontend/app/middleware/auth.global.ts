import { defineNuxtRouteMiddleware, navigateTo } from '#app'
import { useAuthStore } from '~/entities/user'

export default defineNuxtRouteMiddleware(async (to) => {
  // Run only on client – SSR does not have Pinia store
  if (process.client) {
    const auth = useAuthStore()
    await auth.restoreAndValidate()
    if (to.path === '/login' || to.path === '/register' || to.path === '/oauth/callback') return
    if (!auth.user) {
      return navigateTo('/login')
    }
  }
})
