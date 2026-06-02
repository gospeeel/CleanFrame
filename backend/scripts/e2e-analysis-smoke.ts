import * as assert from 'node:assert/strict'
import { exec as execCallback } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import * as path from 'node:path'
import { promisify } from 'node:util'

const exec = promisify(execCallback)

const terminalStatuses = new Set(['DONE', 'FAILED', 'DEAD_LETTER', 'CANCELLED'])

interface AnalysisResponse {
  id: string
  status: string
}

interface AnalysisDetails extends AnalysisResponse {
  maxRating?: string | null
  riskCount?: number
  reviewCount?: number
  processingTime?: number | null
  errorMessage?: string | null
  errorCode?: string | null
}

async function main() {
  const config = {
    apiBase: env('API_BASE', 'http://127.0.0.1:8000'),
    loginOrEmail: env('SMOKE_LOGIN', 'admin'),
    password: env('SMOKE_PASSWORD', 'admin123'),
    files: env('SMOKE_FILES', 'doc/test_script_safe.txt,doc/test_script_safe.txt,doc/test_script_safe.txt')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean),
    timeoutSeconds: Number(env('SMOKE_TIMEOUT_SECONDS', '180')),
    pollIntervalMs: Number(env('SMOKE_POLL_INTERVAL_MS', '3000')),
    restartAfterSeconds: Number(env('SMOKE_RESTART_AFTER_SECONDS', '0')),
    workerRestartCommand: env('WORKER_RESTART_COMMAND', ''),
    requireAllDone: env('SMOKE_REQUIRE_ALL_DONE', 'true') !== 'false'
  }

  assert.ok(config.files.length > 0, 'SMOKE_FILES must contain at least one file')

  const token = await login(config.apiBase, config.loginOrEmail, config.password)
  const submitted = []
  for (const filePath of config.files) {
    submitted.push(await submitAnalysis(config.apiBase, token, filePath))
  }

  const restartPromise = maybeRestartWorker(config.restartAfterSeconds, config.workerRestartCommand)
  const results = await waitForTerminalStatuses({
    apiBase: config.apiBase,
    token,
    ids: submitted.map((item) => item.id),
    timeoutSeconds: config.timeoutSeconds,
    pollIntervalMs: config.pollIntervalMs
  })
  await restartPromise

  if (config.requireAllDone) {
    const notDone = results.filter((item) => item.status !== 'DONE')
    assert.equal(notDone.length, 0, `Expected all analyses DONE, got: ${JSON.stringify(notDone, null, 2)}`)
  }

  console.log(JSON.stringify({
    submitted: submitted.length,
    ids: submitted.map((item) => item.id),
    terminal: results.map((item) => ({
      id: item.id,
      status: item.status,
      maxRating: item.maxRating,
      riskCount: item.riskCount,
      reviewCount: item.reviewCount,
      processingTime: item.processingTime,
      errorCode: item.errorCode,
      errorMessage: item.errorMessage
    }))
  }, null, 2))
}

async function login(apiBase: string, loginOrEmail: string, password: string): Promise<string> {
  const response = await fetchJson<{ accessToken: string }>(`${apiBase}/api/auth/login`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ loginOrEmail, password })
  })
  assert.ok(response.accessToken, 'Login response must contain accessToken')
  return response.accessToken
}

async function submitAnalysis(apiBase: string, token: string, filePath: string): Promise<AnalysisResponse> {
  const buffer = await readFile(filePath)
  const formData = new FormData()
  formData.append('file', new Blob([buffer]), path.basename(filePath))

  const response = await fetchJson<AnalysisResponse>(`${apiBase}/api/analyses`, {
    method: 'POST',
    headers: {
      authorization: `Bearer ${token}`,
      'x-request-id': `e2e-smoke-${Date.now()}-${Math.random().toString(16).slice(2)}`
    },
    body: formData
  })
  assert.ok(response.id, 'Analysis create response must contain id')
  return response
}

async function waitForTerminalStatuses(options: {
  apiBase: string
  token: string
  ids: string[]
  timeoutSeconds: number
  pollIntervalMs: number
}): Promise<AnalysisDetails[]> {
  const deadline = Date.now() + options.timeoutSeconds * 1000
  const latest = new Map<string, AnalysisDetails>()

  while (Date.now() < deadline) {
    await Promise.all(options.ids.map(async (id) => {
      const details = await fetchJson<AnalysisDetails>(`${options.apiBase}/api/analyses/${id}`, {
        headers: { authorization: `Bearer ${options.token}` }
      })
      latest.set(id, details)
    }))

    const results = options.ids.map((id) => latest.get(id)).filter((item): item is AnalysisDetails => Boolean(item))
    if (results.length === options.ids.length && results.every((item) => terminalStatuses.has(item.status))) {
      return results
    }
    await sleep(options.pollIntervalMs)
  }

  throw new Error(`Timed out waiting for terminal statuses: ${JSON.stringify([...latest.values()], null, 2)}`)
}

async function maybeRestartWorker(delaySeconds: number, command: string) {
  if (!delaySeconds || !command) {
    return
  }
  await sleep(delaySeconds * 1000)
  console.log(`Restarting worker with: ${command}`)
  const result = await exec(command, { cwd: path.resolve(__dirname, '../..') })
  if (result.stdout.trim()) {
    console.log(result.stdout.trim())
  }
  if (result.stderr.trim()) {
    console.error(result.stderr.trim())
  }
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const text = await response.text()
  if (!response.ok) {
    throw new Error(`${init?.method ?? 'GET'} ${url} failed ${response.status}: ${text}`)
  }
  return text ? JSON.parse(text) as T : {} as T
}

function env(name: string, fallback: string) {
  return process.env[name] ?? fallback
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

void main().catch((error) => {
  console.error(error)
  process.exit(1)
})
