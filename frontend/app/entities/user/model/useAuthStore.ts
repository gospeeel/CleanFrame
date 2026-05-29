import { useRuntimeConfig } from '#app'
import { defineStore } from 'pinia'
import type { AuthProvider, AuthResponse, UserSession } from './types'

interface ApiError {
  message?: string | string[]
}

const STORAGE_KEY = 'ml_wink_auth'
let refreshPromise: Promise<void> | null = null

function getApiBase() {
  return useRuntimeConfig().public.apiBase
}

function getErrorMessage(error: unknown) {
  const data = (error as { data?: ApiError })?.data
  const message = data?.message

  if (Array.isArray(message)) {
    return message.join(', ')
  }

  return message ?? 'Ошибка авторизации'
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as null | UserSession,
    accessToken: '',
    refreshToken: '',
    expiresIn: 0,
    isRestored: false,
    isRestoring: false
  }),
  getters: {
    token: (state) => state.accessToken
  },
  actions: {
    restore() {
      if (this.isRestored || !process.client) {
        return
      }

      const rawSession = window.localStorage.getItem(STORAGE_KEY)
      if (rawSession) {
        try {
          const session = JSON.parse(rawSession) as AuthResponse
          this.applySession(session)
        } catch {
          window.localStorage.removeItem(STORAGE_KEY)
        }
      }

      this.isRestored = true
    },
    async restoreAndValidate() {
      if (!process.client) {
        return
      }

      this.restore()
      if (this.isRestoring || !this.refreshToken) {
        return
      }

      this.isRestoring = true
      try {
        if (this.accessToken) {
          await this.fetchMe()
          return
        }

        await this.refresh()
      } finally {
        this.isRestoring = false
      }
    },
    applySession(session: AuthResponse) {
      this.user = session.user
      this.accessToken = session.accessToken
      this.refreshToken = session.refreshToken
      this.expiresIn = session.expiresIn
      this.persist()
    },
    applyUser(user: UserSession) {
      this.user = user
      this.persist()
    },
    persist() {
      if (!process.client) {
        return
      }

      if (!this.user || !this.accessToken || !this.refreshToken) {
        window.localStorage.removeItem(STORAGE_KEY)
        return
      }

      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
        accessToken: this.accessToken,
        refreshToken: this.refreshToken,
        expiresIn: this.expiresIn,
        user: this.user
      }))
    },
    async login(payload: { loginOrEmail: string; password: string }) {
      try {
        const session = await $fetch<AuthResponse>(`${getApiBase()}/api/auth/login`, {
          method: 'POST',
          body: payload
        })
        this.applySession(session)
      } catch (error) {
        throw new Error(getErrorMessage(error))
      }
    },
    async register(payload: {
      login: string
      email: string
      password: string
      confirmPassword: string
      inviteToken?: string
    }) {
      try {
        const session = await $fetch<AuthResponse>(`${getApiBase()}/api/auth/register`, {
          method: 'POST',
          body: payload
        })
        this.applySession(session)
      } catch (error) {
        throw new Error(getErrorMessage(error))
      }
    },
    loginWithProvider(provider: Exclude<AuthProvider, 'credentials'>) {
      if (!process.client) {
        return
      }

      window.location.href = `${getApiBase()}/api/auth/oauth/${provider}`
    },
    async fetchMe() {
      if (!this.accessToken) {
        return
      }

      try {
        this.user = await $fetch<UserSession>(`${getApiBase()}/api/auth/me`, {
          headers: {
            Authorization: `Bearer ${this.accessToken}`
          }
        })
        this.persist()
      } catch {
        if (this.refreshToken) {
          await this.refresh()
          return
        }

        await this.logout()
      }
    },
    async refresh() {
      if (!this.refreshToken) {
        await this.logout()
        return
      }

      if (refreshPromise) {
        await refreshPromise
        return
      }

      refreshPromise = this.performRefresh()
      try {
        await refreshPromise
      } finally {
        refreshPromise = null
      }
    },
    async performRefresh() {
      try {
        const session = await $fetch<AuthResponse>(`${getApiBase()}/api/auth/refresh`, {
          method: 'POST',
          body: { refreshToken: this.refreshToken }
        })
        this.applySession(session)
      } catch {
        await this.logout()
      }
    },
    async logout() {
      const token = this.refreshToken
      this.user = null
      this.accessToken = ''
      this.refreshToken = ''
      this.expiresIn = 0
      this.persist()

      if (token) {
        await $fetch(`${getApiBase()}/api/auth/logout`, {
          method: 'POST',
          body: { refreshToken: token }
        }).catch(() => undefined)
      }
    }
  }
})
