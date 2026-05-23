/**
 * AlarmToastProvider
 *
 * Connects to /api/v1/ws/alarms and shows MUI Snackbar toasts whenever an
 * alarm opens or closes.  Mount this once near the root of the app so it
 * works across all pages.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, AlertTitle, Snackbar, Stack } from '@mui/material'
import { AlarmWsPayload, AlarmSeverity } from '../types'
import { buildAlarmWsUrl } from '../utils/apiUrl'

const TOAST_DURATION_MS = 6000
const MAX_TOASTS = 4
const RECONNECT_DELAY_MS = 5000

interface Toast {
  id: string
  type: 'alarm.opened' | 'alarm.closed'
  severity: AlarmSeverity
  alarmName: string
  streamId: number
  matchedClasses: Record<string, number>
}

const MUI_SEVERITY: Record<AlarmSeverity, 'error' | 'warning' | 'info'> = {
  critical: 'error',
  warning: 'warning',
  info: 'info',
}

const AlarmToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return

    const url = buildAlarmWsUrl()
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (evt) => {
      try {
        const msg: AlarmWsPayload = JSON.parse(evt.data)
        if (msg.type === 'heartbeat' || !msg.alarm_name) return
        if (msg.type !== 'alarm.opened' && msg.type !== 'alarm.closed') return

        const toast: Toast = {
          id: `${msg.alarm_id}-${Date.now()}`,
          type: msg.type,
          severity: msg.severity ?? 'warning',
          alarmName: msg.alarm_name,
          streamId: msg.stream_id ?? 0,
          matchedClasses: msg.matched_classes ?? {},
        }
        setToasts((prev) => [toast, ...prev].slice(0, MAX_TOASTS))
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const dismiss = (id: string) => setToasts((prev) => prev.filter((t) => t.id !== id))

  return (
    <>
      {children}
      <Stack spacing={1} sx={{ position: 'fixed', bottom: 24, right: 24, zIndex: 2000, maxWidth: 380, width: '100%' }}>
        {toasts.map((t) => (
          <Snackbar
            key={t.id}
            open
            autoHideDuration={TOAST_DURATION_MS}
            onClose={() => dismiss(t.id)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            sx={{ position: 'relative', mt: 0 }}
          >
            <Alert
              severity={MUI_SEVERITY[t.severity]}
              onClose={() => dismiss(t.id)}
              variant="filled"
              sx={{ width: '100%' }}
            >
              <AlertTitle>
                {t.type === 'alarm.opened' ? '🔔 Alarm opened' : '✅ Alarm closed'} — {t.alarmName}
              </AlertTitle>
              {Object.entries(t.matchedClasses)
                .map(([cls, cnt]) => `${cls} ×${cnt}`)
                .join(', ') || `Stream #${t.streamId}`}
            </Alert>
          </Snackbar>
        ))}
      </Stack>
    </>
  )
}

export default AlarmToastProvider
