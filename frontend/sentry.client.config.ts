import * as Sentry from '@sentry/nuxt'
import { useRuntimeConfig } from '#imports'

const publicConfig = useRuntimeConfig().public
const dsn =
  toOptionalString(publicConfig.glitchtipDsn) ||
  toOptionalString(publicConfig.sentryDsn) ||
  process.env.NUXT_PUBLIC_GLITCHTIP_DSN ||
  process.env.NUXT_PUBLIC_SENTRY_DSN
const tracesSampleRate =
  toOptionalString(publicConfig.glitchtipTracesSampleRate) ||
  toOptionalString(publicConfig.sentryTracesSampleRate) ||
  process.env.NUXT_PUBLIC_GLITCHTIP_TRACES_SAMPLE_RATE ||
  process.env.NUXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ||
  '0.1'
const privacyMode =
  toOptionalString(publicConfig.privacyMode) || process.env.NUXT_PUBLIC_PRIVACY_MODE || 'false'
const SENSITIVE_KEY_PATTERN = /authorization|cookie|token|password|secret|code/i
const PRIVATE_KEY_PATTERN = /filename|file_name|originalname|email/i

if (dsn) {
  Sentry.init({
    dsn,
    environment:
      toOptionalString(publicConfig.appEnv) ||
      process.env.NUXT_PUBLIC_APP_ENV ||
      process.env.NODE_ENV ||
      'development',
    release: toOptionalString(publicConfig.appVersion) || process.env.NUXT_PUBLIC_APP_VERSION,
    tracesSampleRate: Number(tracesSampleRate),
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
      (privacyMode === 'true' && PRIVATE_KEY_PATTERN.test(key))
    ) {
      result[key] = '[Filtered]'
      continue
    }

    result[key] = scrubObject(entry)
  }

  return result
}

function toOptionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined
}
