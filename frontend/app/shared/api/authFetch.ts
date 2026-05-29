import { useAuthStore } from '~/entities/user'

type FetchOptions = Parameters<typeof $fetch>[1]

function isUnauthorized(error: unknown) {
  const statusCode = (error as { statusCode?: number; response?: { status?: number } })?.statusCode
  const responseStatus = (error as { response?: { status?: number } })?.response?.status
  return statusCode === 401 || responseStatus === 401
}

function mergeHeaders(options: FetchOptions | undefined, token: string) {
  return {
    ...(options?.headers ?? {}),
    Authorization: `Bearer ${token}`
  }
}

export async function authFetch<T>(url: string, options: FetchOptions = {}) {
  const auth = useAuthStore()

  if (!auth.token && auth.refreshToken) {
    await auth.refresh()
  }

  try {
    return await $fetch<T>(url, {
      ...options,
      headers: mergeHeaders(options, auth.token)
    })
  } catch (error) {
    if (!isUnauthorized(error) || !auth.refreshToken) {
      throw error
    }

    await auth.refresh()

    if (!auth.token) {
      throw error
    }

    return await $fetch<T>(url, {
      ...options,
      headers: mergeHeaders(options, auth.token)
    })
  }
}
