export function isPrivacyModeEnabled(value: unknown) {
  return String(value ?? '').toLowerCase() === 'true'
}

export function privateFileLabel(id: string | null | undefined) {
  return `Файл #${shortId(id)}`
}

export function displayFileName(fileName: string, id: string | null | undefined, privacyMode: boolean) {
  return privacyMode ? privateFileLabel(id) : fileName
}

export function displayUserIdentity(login: string, email: string, id: string | null | undefined, privacyMode: boolean) {
  return privacyMode ? `Пользователь #${shortId(id || login || email)}` : `${login} · ${email}`
}

export function displayNotificationMessage(message: string, analysisId: string | null | undefined, privacyMode: boolean) {
  if (!privacyMode) {
    return message
  }

  const separator = message.indexOf(':')
  if (separator < 0) {
    return message
  }

  return `${privateFileLabel(analysisId)}:${message.slice(separator + 1)}`
}

function shortId(id: string | null | undefined) {
  const value = String(id || 'analysis').replace(/[^a-zA-Z0-9]/g, '')
  return value.slice(0, 8) || 'analysis'
}
