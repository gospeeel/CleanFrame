export default defineNuxtConfig({
  compatibilityDate: '2026-04-29',
  devtools: { enabled: process.env.NUXT_DEVTOOLS === 'true' },
  modules: [
    '@sentry/nuxt/module',
    '@nuxtjs/tailwindcss',
    '@pinia/nuxt',
    '@peterbud/nuxt-query'
  ],
  app: {
    head: {
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Newsreader:opsz,wght@6..72,500;6..72,600;6..72,700&display=swap'
        }
      ]
    }
  },
  sentry: {
    telemetry: false,
    sourcemaps: {
      disable: !process.env.SENTRY_AUTH_TOKEN
    },
    release: process.env.NUXT_PUBLIC_APP_VERSION
      ? { name: process.env.NUXT_PUBLIC_APP_VERSION }
      : undefined
  },
  css: ['~/shared/assets/css/main.css'],
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000',
      glitchtipDsn: process.env.NUXT_PUBLIC_GLITCHTIP_DSN || '',
      glitchtipTracesSampleRate: process.env.NUXT_PUBLIC_GLITCHTIP_TRACES_SAMPLE_RATE || '0.1',
      sentryDsn: process.env.NUXT_PUBLIC_SENTRY_DSN || '',
      sentryTracesSampleRate: process.env.NUXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE || '0.1',
      appEnv: process.env.NUXT_PUBLIC_APP_ENV || process.env.NODE_ENV || 'development',
      appVersion: process.env.NUXT_PUBLIC_APP_VERSION || '',
      privacyMode: process.env.NUXT_PUBLIC_PRIVACY_MODE || 'false'
    }
  },
  typescript: {
    typeCheck: false
  }
})
