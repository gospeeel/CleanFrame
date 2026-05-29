import * as Sentry from '@sentry/nestjs'

const SENSITIVE_KEY_PATTERN = /authorization|cookie|token|password|secret|code/i
const PRIVATE_KEY_PATTERN = /filename|file_name|originalname|email/i
const dsn = process.env.GLITCHTIP_DSN ?? process.env.SENTRY_DSN

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.APP_ENV ?? process.env.NODE_ENV ?? 'development',
    release: process.env.APP_VERSION,
    tracesSampleRate: Number(process.env.GLITCHTIP_TRACES_SAMPLE_RATE ?? process.env.SENTRY_TRACES_SAMPLE_RATE ?? '0.1'),
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
    if (SENSITIVE_KEY_PATTERN.test(key) || (process.env.PRIVACY_MODE === 'true' && PRIVATE_KEY_PATTERN.test(key))) {
      result[key] = '[Filtered]'
      continue
    }

    result[key] = scrubObject(entry)
  }

  return result
}
