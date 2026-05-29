import * as Sentry from '@sentry/nestjs'

type MetricAttributes = Record<string, string | number | boolean | null | undefined>

const METRIC_PREFIX = 'clean_frame.analysis'

export function countQueueMetric(name: string, value = 1, attributes: MetricAttributes = {}) {
  Sentry.metrics.count(`${METRIC_PREFIX}.${name}`, value, {
    attributes: cleanAttributes(attributes)
  })
}

export function distributionQueueMetric(
  name: string,
  value: number | null | undefined,
  unit: string,
  attributes: MetricAttributes = {}
) {
  if (!Number.isFinite(value)) {
    return
  }

  Sentry.metrics.distribution(`${METRIC_PREFIX}.${name}`, value as number, {
    unit,
    attributes: cleanAttributes(attributes)
  })
}

export function gaugeQueueMetric(
  name: string,
  value: number | null | undefined,
  unit: string,
  attributes: MetricAttributes = {}
) {
  if (!Number.isFinite(value)) {
    return
  }

  Sentry.metrics.gauge(`${METRIC_PREFIX}.${name}`, value as number, {
    unit,
    attributes: cleanAttributes(attributes)
  })
}

export function breadcrumbQueueMetric(message: string, data: MetricAttributes = {}) {
  Sentry.addBreadcrumb({
    category: 'analysis.queue.metrics',
    message,
    level: 'info',
    data: cleanAttributes(data)
  })
}

function cleanAttributes(attributes: MetricAttributes) {
  return Object.fromEntries(
    Object.entries(attributes).filter(([, value]) => value !== undefined && value !== null)
  ) as Record<string, string | number | boolean>
}
