import { useAuthStore } from '~/entities/user'

export default defineNuxtPlugin(() => {
  const auth = useAuthStore()
  auth.restore()
})
