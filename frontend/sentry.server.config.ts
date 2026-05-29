import * as Sentry from '@sentry/nuxt'

const dsn = process.env.NUXT_PUBLIC_GLITCHTIP_DSN || process.env.NUXT_PUBLIC_SENTRY_DSN
const SENSITIVE_KEY_PATTERN = /authorization|cookie|token|password|secret|code/i
const PRIVATE_KEY_PATTERN = /filename|file_name|originalname|email/i

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NUXT_PUBLIC_APP_ENV || process.env.NODE_ENV || 'development',
    release: process.env.NUXT_PUBLIC_APP_VERSION,
    tracesSampleRate: Number(
      process.env.NUXT_PUBLIC_GLITCHTIP_TRACES_SAMPLE_RATE ||
      process.env.NUXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ||
      '0.1'
    ),
    beforeSend(event) {
      if (event.request?.headers) {
        delete event.request.headers.authorization
        delete event.request.headers.cookie
      }
      if (event.request) {
        delete event.request.data
        delete event.request.cookies
      }
      event.contexts = scrubObject(event.contexts) as typeof event.contexts
      event.extra = scrubObject(event.extra) as typeof event.extra

      return event
    }
  })
}

function scrubObject(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => scrubObject(item))
  }

  if (!value || typeof value !== 'object') {
    return value
  }

  const result: Record<string, unknown> = {}
  for (const [key, entry] of Object.entries(value)) {
    if (
      SENSITIVE_KEY_PATTERN.test(key) ||
      (process.env.NUXT_PUBLIC_PRIVACY_MODE === 'true' && PRIVATE_KEY_PATTERN.test(key))
    ) {
      result[key] = '[Filtered]'
      continue
    }

    result[key] = scrubObject(entry)
  }

  return result
}
