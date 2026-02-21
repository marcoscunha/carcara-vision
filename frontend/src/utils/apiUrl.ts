const DEFAULT_API_BASE_URL = '/api/v1'

function stripTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '')
}

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_URL?.trim()
  if (!configured) {
    return DEFAULT_API_BASE_URL
  }
  return stripTrailingSlash(configured)
}

export function buildDetectionsWsUrl(streamId: number): string {
  const apiBase = getApiBaseUrl()

  if (/^https?:\/\//i.test(apiBase)) {
    const wsBase = apiBase.replace(/^http/i, 'ws')
    return `${wsBase}/ws/streams/${streamId}/detections`
  }

  const normalizedBase = apiBase.startsWith('/') ? apiBase : `/${apiBase}`
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${wsProtocol}//${window.location.host}${normalizedBase}/ws/streams/${streamId}/detections`
}
