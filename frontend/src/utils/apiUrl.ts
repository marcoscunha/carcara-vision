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

export function buildAlarmWsUrl(): string {
  const apiBase = getApiBaseUrl()

  if (/^https?:\/\//i.test(apiBase)) {
    const wsBase = apiBase.replace(/^http/i, 'ws')
    return `${wsBase}/ws/alarms`
  }

  const normalizedBase = apiBase.startsWith('/') ? apiBase : `/${apiBase}`
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${wsProtocol}//${window.location.host}${normalizedBase}/ws/alarms`
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

export function buildSnapshotUrl(streamId: number): string {
  const base = getApiBaseUrl()
  return `${base}/streams/${streamId}/snapshot`
}

export function buildAlarmEventSnapshotUrl(eventId: number): string {
  const base = getApiBaseUrl()
  return `${base}/alarms/events/${eventId}/snapshot`
}
