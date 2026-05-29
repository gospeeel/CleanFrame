import { defineNuxtRouteMiddleware, navigateTo } from '#app'
import { useAuthStore } from '~/entities/user'

const PUBLIC_PATHS = new Set([
  '/login',
  '/register',
  '/oauth/callback',
  '/unauthorized',
  '/forbidden',
  '/not-found'
])

export default defineNuxtRouteMiddleware(async (to) => {
  // Run only on client – SSR does not have Pinia store
  if (process.client) {
    const auth = useAuthStore()
    await auth.restoreAndValidate()
    if (PUBLIC_PATHS.has(to.path) || to.name === 'slug') return
    if (!auth.user) {
      return navigateTo({
        path: '/unauthorized',
        query: { redirect: to.fullPath }
      })
    }
  }
})
