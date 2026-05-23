import React, { useState } from 'react'
import {
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  CardMedia,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
  Slider,
  Switch,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import {
  Add as AddIcon,
  CheckCircle as AckIcon,
  Circle as CircleIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  HelpOutline as HelpIcon,
  ImageNotSupported as NoImageIcon,
  Notifications as NotificationsIcon,
  NotificationsActive as OpenIcon,
  Place as ZoneIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material'
import {
  useAlarms,
  useCreateAlarm,
  useUpdateAlarm,
  useDeleteAlarm,
  useStreams,
  useAlarmZones,
  useCreateAlarmZone,
  useDeleteAlarmZone,
  useAlarmEvents,
  useAckAlarmEvent,
  useDeleteAlarmEvent,
} from '../hooks/useQueries'
import {
  Alarm,
  AlarmCreate,
  AlarmZone,
  AlarmEvent,
  AlarmEventState,
  AlarmSeverity,
  TriggerConfig,
  TriggerType,
  Stream,
  ScheduleWindow,
  NotifyChannel,
} from '../types'
import { getStreamClassNames } from '../utils/cocoClasses'
import { buildSnapshotUrl, buildAlarmEventSnapshotUrl } from '../utils/apiUrl'
import { PolygonEditorDialog } from '../components/PolygonEditorDialog'

// ─── helpers ──────────────────────────────────────────────────────────────────

const SEVERITY_COLORS: Record<AlarmSeverity, 'default' | 'info' | 'warning' | 'error'> = {
  info: 'info',
  warning: 'warning',
  critical: 'error',
}

const STATE_COLORS: Record<AlarmEventState, 'default' | 'error' | 'success' | 'warning'> = {
  open: 'error',
  closed: 'success',
  acknowledged: 'warning',
  resolved: 'default',
}

const TRIGGER_LABELS: Record<TriggerType, string> = {
  class_present: 'Class Present',
  class_count: 'Class Count',
  class_absent_for: 'Class Absent For',
  zone_enter: 'Zone Enter',
  dwell: 'Dwell',
}

function fmtDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

// ─── default form state ────────────────────────────────────────────────────────

interface AlarmFormState {
  name: string
  stream_id: number
  severity: AlarmSeverity
  trigger_type: TriggerType
  /** Single class selected in the UI — wrapped into class_names[] on submit */
  class_name: string
  confidence_threshold: number
  count_op: '>=' | '>' | '==' | '<=' | '<'
  count_threshold: number
  absent_seconds: number
  dwell_seconds: number
  zone_id: string
  is_active: boolean
  store_events: boolean
  min_on_seconds: number
  min_off_seconds: number
  cooldown_seconds: number
  notify_ws: boolean
  notify_webhook: boolean
  webhook_url: string
  schedule: ScheduleWindow[]
}

const EMPTY_FORM: AlarmFormState = {
  name: '',
  stream_id: 0,
  severity: 'warning',
  trigger_type: 'class_present',
  class_name: '',
  confidence_threshold: 0.5,
  count_op: '>=',
  count_threshold: 1,
  absent_seconds: 60,
  dwell_seconds: 5,
  zone_id: '',
  is_active: true,
  store_events: true,
  min_on_seconds: 0,
  min_off_seconds: 5,
  cooldown_seconds: 30,
  notify_ws: true,
  notify_webhook: false,
  webhook_url: '',
  schedule: [],
}

function alarmToForm(alarm: Alarm): AlarmFormState {
  const tc = alarm.trigger_config
  return {
    name: alarm.name,
    stream_id: alarm.stream_id,
    severity: alarm.severity,
    trigger_type: alarm.trigger_type,
    class_name: tc.class_names[0] ?? '',
    confidence_threshold: tc.min_confidence,
    count_op: tc.type === 'class_count' ? tc.count_op : '>=',
    count_threshold: tc.type === 'class_count' ? tc.count_threshold : 1,
    absent_seconds: tc.type === 'class_absent_for' ? tc.absent_seconds : 60,
    dwell_seconds: tc.type === 'dwell' ? tc.dwell_seconds : 5,
    zone_id: alarm.zone_id != null ? String(alarm.zone_id) : '',
    is_active: alarm.is_active,
    store_events: alarm.store_events,
    min_on_seconds: alarm.min_on_seconds,
    min_off_seconds: alarm.min_off_seconds,
    cooldown_seconds: alarm.cooldown_seconds,
    notify_ws: alarm.notify_channels.includes('ws'),
    notify_webhook: alarm.notify_channels.includes('webhook'),
    webhook_url: alarm.webhook_url ?? '',
    schedule: alarm.schedule ?? [],
  }
}

function formToPayload(f: AlarmFormState): AlarmCreate {
  const class_names = f.class_name ? [f.class_name] : []
  let trigger_config: TriggerConfig
  if (f.trigger_type === 'class_count') {
    trigger_config = {
      type: 'class_count',
      class_names,
      min_confidence: f.confidence_threshold,
      count_op: f.count_op,
      count_threshold: f.count_threshold,
    }
  } else if (f.trigger_type === 'class_absent_for') {
    trigger_config = {
      type: 'class_absent_for',
      class_names,
      min_confidence: f.confidence_threshold,
      absent_seconds: f.absent_seconds,
    }
  } else if (f.trigger_type === 'zone_enter') {
    trigger_config = {
      type: 'zone_enter',
      class_names,
      min_confidence: f.confidence_threshold,
    }
  } else if (f.trigger_type === 'dwell') {
    trigger_config = {
      type: 'dwell',
      class_names,
      min_confidence: f.confidence_threshold,
      dwell_seconds: f.dwell_seconds,
    }
  } else {
    trigger_config = {
      type: 'class_present',
      class_names,
      min_confidence: f.confidence_threshold,
    }
  }
  const channels: NotifyChannel[] = []
  if (f.notify_ws) channels.push('ws')
  if (f.notify_webhook) channels.push('webhook')
  return {
    stream_id: f.stream_id,
    name: f.name,
    severity: f.severity,
    trigger_config,
    zone_id: f.zone_id !== '' ? Number(f.zone_id) : null,
    is_active: f.is_active,
    store_events: f.store_events,
    min_on_seconds: f.min_on_seconds,
    min_off_seconds: f.min_off_seconds,
    cooldown_seconds: f.cooldown_seconds,
    notify_channels: channels,
    webhook_url: f.notify_webhook ? f.webhook_url || null : null,
    schedule: f.schedule.length > 0 ? f.schedule : null,
  }
}

// ─── Zone dialog ──────────────────────────────────────────────────────────────

// ─── Alarm rule dialog ────────────────────────────────────────────────────────

interface AlarmDialogProps {
  open: boolean
  editing: Alarm | null
  streams: Stream[]
  onClose: () => void
}

const AlarmDialog: React.FC<AlarmDialogProps> = ({ open, editing, streams, onClose }) => {
  const [form, setForm] = useState<AlarmFormState>(editing ? alarmToForm(editing) : EMPTY_FORM)
  const [previewKey, setPreviewKey] = useState(0)
  const { data: zonesData } = useAlarmZones(form.stream_id)
  const zones = Array.isArray(zonesData) ? (zonesData as AlarmZone[]) : []
  const createMutation = useCreateAlarm()
  const updateMutation = useUpdateAlarm()
  const createZoneMutation = useCreateAlarmZone()
  const deleteZoneMutation = useDeleteAlarmZone()

  // Inline zone creation state
  const [newZoneName, setNewZoneName] = useState('')
  const [newZoneStep, setNewZoneStep] = useState<'idle' | 'naming' | 'drawing'>('idle')
  const [newZonePolygon, setNewZonePolygon] = useState<[number, number][]>([])

  React.useEffect(() => {
    if (!open) {
      setNewZoneName('')
      setNewZoneStep('idle')
      setNewZonePolygon([])
    }
  }, [open])

  React.useEffect(() => {
    setForm(editing ? alarmToForm(editing) : EMPTY_FORM)
  }, [editing, open])

  const set = <K extends keyof AlarmFormState>(key: K, val: AlarmFormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: val }))

  const selectedStream = streams.find((s) => s.id === form.stream_id) ?? null
  const classOptions = getStreamClassNames(selectedStream)
  const zoneRequired = form.trigger_type === 'zone_enter' || form.trigger_type === 'dwell'
  const zoneInvalid = zoneRequired && !form.zone_id

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (zoneInvalid) return
    const payload = formToPayload(form)
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: payload }, { onSuccess: onClose })
    } else {
      createMutation.mutate(payload, { onSuccess: onClose })
    }
  }

  return (
    <>
      <Dialog open={open && newZoneStep !== 'drawing'} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? 'Edit Alarm Rule' : 'New Alarm Rule'}</DialogTitle>
        <form onSubmit={handleSubmit}>
          <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
            {/* Basic info */}
            <TextField
              size="small"
              label="Name"
              required
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
            />
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
              <FormControl size="small" fullWidth>
                <InputLabel>Stream</InputLabel>
                <Select
                  value={form.stream_id}
                  label="Stream"
                  onChange={(e) => {
                    set('stream_id', Number(e.target.value))
                    setPreviewKey(0)
                  }}
                >
                  {streams.map((s) => (
                    <MenuItem key={s.id} value={s.id}>
                      {s.stream_name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" fullWidth>
                <InputLabel>Severity</InputLabel>
                <Select
                  value={form.severity}
                  label="Severity"
                  onChange={(e) => set('severity', e.target.value as AlarmSeverity)}
                >
                  <MenuItem value="info">Info</MenuItem>
                  <MenuItem value="warning">Warning</MenuItem>
                  <MenuItem value="critical">Critical</MenuItem>
                </Select>
              </FormControl>
            </Box>

            {form.stream_id > 0 && (
              <Box sx={{ position: 'relative', borderRadius: 1, overflow: 'hidden', bgcolor: 'grey.900', height: 160 }}>
                <img
                  key={`preview-${form.stream_id}-${previewKey}`}
                  src={buildSnapshotUrl(form.stream_id)}
                  alt="Stream preview"
                  style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                  onError={(e) => {
                    ;(e.target as HTMLImageElement).style.display = 'none'
                  }}
                />
                <Tooltip title="Refresh preview">
                  <IconButton
                    size="small"
                    onClick={() => setPreviewKey((k) => k + 1)}
                    sx={{
                      position: 'absolute',
                      top: 4,
                      right: 4,
                      bgcolor: 'rgba(0,0,0,0.5)',
                      color: 'white',
                      '&:hover': { bgcolor: 'rgba(0,0,0,0.7)' },
                    }}
                  >
                    <RefreshIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            )}

            <Divider>Trigger</Divider>

            {/* Trigger type */}
            <FormControl size="small" fullWidth>
              <InputLabel>Trigger type</InputLabel>
              <Select
                value={form.trigger_type}
                label="Trigger type"
                onChange={(e) => {
                  const t = e.target.value as TriggerType
                  set('trigger_type', t)
                }}
              >
                {(Object.keys(TRIGGER_LABELS) as TriggerType[]).map((t) => (
                  <MenuItem key={t} value={t}>
                    {TRIGGER_LABELS[t]}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
              {classOptions ? (
                <Autocomplete
                  size="small"
                  options={classOptions}
                  value={form.class_name || null}
                  onChange={(_, v) => set('class_name', v ?? '')}
                  renderInput={(params) => <TextField {...params} label="Detection class" required />}
                />
              ) : (
                <TextField
                  size="small"
                  label="Class name"
                  required
                  value={form.class_name}
                  onChange={(e) => set('class_name', e.target.value)}
                  helperText={!form.stream_id ? 'Select a stream first' : undefined}
                />
              )}
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Confidence: {(form.confidence_threshold * 100).toFixed(0)}%
                </Typography>
                <Slider
                  size="small"
                  min={0.1}
                  max={1}
                  step={0.05}
                  value={form.confidence_threshold}
                  onChange={(_, v) => set('confidence_threshold', v as number)}
                />
              </Box>
            </Box>

            {form.trigger_type === 'class_count' && (
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                <FormControl size="small" fullWidth>
                  <InputLabel>Condition</InputLabel>
                  <Select
                    value={form.count_op}
                    label="Condition"
                    onChange={(e) => set('count_op', e.target.value as AlarmFormState['count_op'])}
                  >
                    {(
                      ['>= (at least)', '> (more than)', '== (exactly)', '<= (at most)', '< (fewer than)'] as const
                    ).map((label, i) => {
                      const op = (['>=', '>', '==', '<=', '<'] as const)[i]
                      return (
                        <MenuItem key={op} value={op}>
                          {label}
                        </MenuItem>
                      )
                    })}
                  </Select>
                </FormControl>
                <TextField
                  size="small"
                  type="number"
                  label="Count threshold"
                  value={form.count_threshold}
                  onChange={(e) => set('count_threshold', Number(e.target.value))}
                  inputProps={{ min: 0 }}
                />
              </Box>
            )}

            {form.trigger_type === 'class_absent_for' && (
              <TextField
                size="small"
                type="number"
                label="Absent for (seconds)"
                value={form.absent_seconds}
                onChange={(e) => set('absent_seconds', Number(e.target.value))}
                inputProps={{ min: 1 }}
              />
            )}

            {form.trigger_type === 'dwell' && (
              <TextField
                size="small"
                type="number"
                label="Dwell seconds"
                value={form.dwell_seconds}
                onChange={(e) => set('dwell_seconds', Number(e.target.value))}
                inputProps={{ min: 1, step: 0.5 }}
                helperText="Track must remain inside the zone for this long before firing."
              />
            )}

            {/* Zone — inline picker with create */}
            {form.stream_id > 0 && (
              <Box>
                <Typography
                  variant="caption"
                  color={zoneRequired && !form.zone_id ? 'error' : 'text.secondary'}
                  sx={{ mb: 0.75, display: 'block' }}
                >
                  {zoneRequired ? 'Zone (required)' : 'Zone (optional)'}
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, alignItems: 'center' }}>
                  {!zoneRequired && (
                    <Chip
                      label="Whole frame"
                      size="small"
                      variant={!form.zone_id ? 'filled' : 'outlined'}
                      color={!form.zone_id ? 'primary' : 'default'}
                      onClick={() => set('zone_id', '')}
                    />
                  )}
                  {zones.map((z: AlarmZone) => (
                    <Chip
                      key={z.id}
                      label={z.name}
                      size="small"
                      variant={form.zone_id === String(z.id) ? 'filled' : 'outlined'}
                      color={form.zone_id === String(z.id) ? 'primary' : 'default'}
                      onClick={() => set('zone_id', String(z.id))}
                      onDelete={() => {
                        deleteZoneMutation.mutate({ id: z.id, streamId: form.stream_id })
                        if (form.zone_id === String(z.id)) set('zone_id', '')
                      }}
                    />
                  ))}
                  {newZoneStep === 'idle' && (
                    <Chip
                      label="＋ New zone"
                      size="small"
                      variant="outlined"
                      onClick={() => setNewZoneStep('naming')}
                    />
                  )}
                </Box>

                {/* Inline new-zone mini-form */}
                {newZoneStep !== 'idle' && (
                  <Box sx={{ mt: 1, display: 'flex', gap: 1, alignItems: 'center' }}>
                    <TextField
                      size="small"
                      label="Zone name"
                      value={newZoneName}
                      onChange={(e) => setNewZoneName(e.target.value)}
                      sx={{ flex: 1 }}
                      autoFocus
                    />
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<ZoneIcon />}
                      disabled={!newZoneName.trim()}
                      onClick={() => setNewZoneStep('drawing')}
                    >
                      {newZonePolygon.length >= 3 ? `Polygon (${newZonePolygon.length} pts)` : 'Draw'}
                    </Button>
                    <Button
                      size="small"
                      variant="contained"
                      disabled={!newZoneName.trim() || newZonePolygon.length < 3 || createZoneMutation.isPending}
                      onClick={() => {
                        createZoneMutation.mutate(
                          { stream_id: form.stream_id, name: newZoneName.trim(), polygon: newZonePolygon },
                          {
                            onSuccess: (created) => {
                              set('zone_id', String((created as unknown as AlarmZone).id))
                              setNewZoneName('')
                              setNewZoneStep('idle')
                              setNewZonePolygon([])
                            },
                          },
                        )
                      }}
                    >
                      Save
                    </Button>
                    <IconButton
                      size="small"
                      onClick={() => {
                        setNewZoneStep('idle')
                        setNewZoneName('')
                        setNewZonePolygon([])
                      }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Box>
                )}

                {zoneRequired && !form.zone_id && (
                  <Typography variant="caption" color="error" sx={{ mt: 0.5, display: 'block' }}>
                    Zone is required for this trigger type
                  </Typography>
                )}
              </Box>
            )}

            <Divider>Hysteresis</Divider>

            {form.trigger_type !== 'class_absent_for' && (
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      Min ON: {form.min_on_seconds}s
                    </Typography>
                    <Tooltip title="Debounce: alarm only opens after the condition is true for this many consecutive seconds. Prevents flickering from brief detections.">
                      <HelpIcon sx={{ fontSize: 14, color: 'text.disabled', cursor: 'help' }} />
                    </Tooltip>
                  </Box>
                  <Slider
                    size="small"
                    min={0}
                    max={30}
                    step={1}
                    value={form.min_on_seconds}
                    onChange={(_, v) => set('min_on_seconds', v as number)}
                  />
                </Box>
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      Min OFF: {form.min_off_seconds}s
                    </Typography>
                    <Tooltip title="Grace period: alarm only closes after the condition has been false for this many consecutive seconds. Prevents premature closing when the subject briefly leaves the frame.">
                      <HelpIcon sx={{ fontSize: 14, color: 'text.disabled', cursor: 'help' }} />
                    </Tooltip>
                  </Box>
                  <Slider
                    size="small"
                    min={0}
                    max={60}
                    step={1}
                    value={form.min_off_seconds}
                    onChange={(_, v) => set('min_off_seconds', v as number)}
                  />
                </Box>
              </Box>
            )}
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  Cooldown: {form.cooldown_seconds}s
                </Typography>
                <Tooltip title="Suppression: after an alarm closes, it cannot re-open for this many seconds. Prevents alarm storms from rapidly repeating conditions.">
                  <HelpIcon sx={{ fontSize: 14, color: 'text.disabled', cursor: 'help' }} />
                </Tooltip>
              </Box>
              <Slider
                size="small"
                min={0}
                max={300}
                step={5}
                value={form.cooldown_seconds}
                onChange={(_, v) => set('cooldown_seconds', v as number)}
              />
            </Box>

            <Divider>Schedule</Divider>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Optional weekly windows. If none, alarm is always armed.
              </Typography>
              {form.schedule.map((win, idx) => (
                <Box
                  key={idx}
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 0.5,
                    p: 1,
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: 1,
                  }}
                >
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((label, day) => {
                      const checked = win.weekdays.includes(day)
                      return (
                        <FormControlLabel
                          key={day}
                          sx={{ mr: 1 }}
                          control={
                            <Switch
                              size="small"
                              checked={checked}
                              onChange={(e) => {
                                const next = [...form.schedule]
                                const wds = new Set(next[idx].weekdays)
                                if (e.target.checked) wds.add(day)
                                else wds.delete(day)
                                next[idx] = { ...next[idx], weekdays: Array.from(wds).sort() }
                                set('schedule', next)
                              }}
                            />
                          }
                          label={label}
                        />
                      )
                    })}
                  </Box>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <TextField
                      size="small"
                      type="number"
                      label="Start hour"
                      value={win.start_hour}
                      onChange={(e) => {
                        const next = [...form.schedule]
                        next[idx] = { ...next[idx], start_hour: Math.max(0, Math.min(23, Number(e.target.value))) }
                        set('schedule', next)
                      }}
                      inputProps={{ min: 0, max: 23 }}
                    />
                    <TextField
                      size="small"
                      type="number"
                      label="End hour"
                      value={win.end_hour}
                      onChange={(e) => {
                        const next = [...form.schedule]
                        next[idx] = { ...next[idx], end_hour: Math.max(1, Math.min(24, Number(e.target.value))) }
                        set('schedule', next)
                      }}
                      inputProps={{ min: 1, max: 24 }}
                    />
                    <IconButton
                      size="small"
                      onClick={() =>
                        set(
                          'schedule',
                          form.schedule.filter((_, i) => i !== idx),
                        )
                      }
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Box>
                </Box>
              ))}
              <Button
                size="small"
                startIcon={<AddIcon />}
                onClick={() =>
                  set('schedule', [...form.schedule, { weekdays: [0, 1, 2, 3, 4], start_hour: 8, end_hour: 18 }])
                }
              >
                Add window
              </Button>
            </Box>

            <Divider>Options</Divider>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              <FormControlLabel
                control={<Switch checked={form.is_active} onChange={(e) => set('is_active', e.target.checked)} />}
                label="Active"
              />
              <FormControlLabel
                control={<Switch checked={form.store_events} onChange={(e) => set('store_events', e.target.checked)} />}
                label="Store events"
              />
              <FormControlLabel
                control={<Switch checked={form.notify_ws} onChange={(e) => set('notify_ws', e.target.checked)} />}
                label="Live WS notifications"
              />
              <FormControlLabel
                control={
                  <Switch checked={form.notify_webhook} onChange={(e) => set('notify_webhook', e.target.checked)} />
                }
                label="Webhook"
              />
            </Box>
            {form.notify_webhook && (
              <TextField
                size="small"
                label="Webhook URL"
                placeholder="https://example.com/hook"
                value={form.webhook_url}
                onChange={(e) => set('webhook_url', e.target.value)}
              />
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={onClose}>Cancel</Button>
            <Button
              type="submit"
              variant="contained"
              disabled={createMutation.isPending || updateMutation.isPending || zoneInvalid}
            >
              {editing ? 'Update' : 'Create'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>

      {/* Polygon editor for inline zone creation */}
      {selectedStream && newZoneStep === 'drawing' && (
        <PolygonEditorDialog
          open
          title={`Draw zone — ${newZoneName || 'New zone'}`}
          imageUrl={buildSnapshotUrl(form.stream_id)}
          initialPolygon={newZonePolygon.length > 0 ? newZonePolygon : undefined}
          onSave={(poly) => {
            setNewZonePolygon(poly)
            setNewZoneStep('naming')
          }}
          onCancel={() => setNewZoneStep('naming')}
        />
      )}
    </>
  )
}

// ─── Main page ─────────────────────────────────────────────────────────────────

const Alarms: React.FC = () => {
  const [tab, setTab] = useState(0)
  const [alarmDialogOpen, setAlarmDialogOpen] = useState(false)
  const [editingAlarm, setEditingAlarm] = useState<Alarm | null>(null)
  const [filterStreamId, setFilterStreamId] = useState<number>(0)
  const [filterState, setFilterState] = useState<string>('')

  const { data: streamsData, isLoading: streamsLoading } = useStreams()
  const streams = Array.isArray(streamsData) ? (streamsData as Stream[]) : []

  const { data: alarmsData, isLoading: alarmsLoading } = useAlarms(filterStreamId || undefined)
  const alarmList = Array.isArray(alarmsData) ? (alarmsData as Alarm[]) : []

  const { data: eventsData, isLoading: eventsLoading } = useAlarmEvents({
    stream_id: filterStreamId || undefined,
    state: filterState || undefined,
    limit: 100,
  })
  const eventList = Array.isArray(eventsData) ? (eventsData as AlarmEvent[]) : []

  const deleteMutation = useDeleteAlarm()
  const ackMutation = useAckAlarmEvent()
  const deleteEventMutation = useDeleteAlarmEvent()

  const openAlarmDialog = (alarm?: Alarm) => {
    setEditingAlarm(alarm ?? null)
    setAlarmDialogOpen(true)
  }

  if (streamsLoading) {
    return (
      <Box>
        <Skeleton variant="text" width={200} height={40} />
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 2, mt: 2 }}>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} variant="rounded" height={150} />
          ))}
        </Box>
      </Box>
    )
  }

  return (
    <Box className="fade-in">
      {/* Page header */}
      <Box className="page-header">
        <Box>
          <Typography variant="h4" className="page-header__title">
            Alarms
          </Typography>
          <Typography variant="body2" color="text.secondary" className="page-header__subtitle">
            Detection rules, zones, and event history
          </Typography>
        </Box>
        <Box className="page-header__actions" sx={{ display: 'flex', gap: 1 }}>
          {tab === 0 && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => openAlarmDialog()}>
              New Rule
            </Button>
          )}
        </Box>
      </Box>

      {/* Stream filter */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center' }}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Filter by stream</InputLabel>
          <Select
            value={filterStreamId}
            label="Filter by stream"
            onChange={(e) => setFilterStreamId(Number(e.target.value))}
          >
            <MenuItem value={0}>All streams</MenuItem>
            {streams.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                {s.stream_name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        {tab === 1 && (
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>State</InputLabel>
            <Select value={filterState} label="State" onChange={(e) => setFilterState(e.target.value)}>
              <MenuItem value="">All states</MenuItem>
              <MenuItem value="open">Open</MenuItem>
              <MenuItem value="closed">Closed</MenuItem>
              <MenuItem value="acknowledged">Acknowledged</MenuItem>
            </Select>
          </FormControl>
        )}
      </Box>

      {/* Tabs */}
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label={`Rules (${alarmList.length})`} />
        <Tab label={`Events (${eventList.length})`} />
      </Tabs>

      {/* ── Tab 0: Rules ─── */}
      {tab === 0 && (
        <>
          {alarmsLoading ? (
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 2 }}>
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} variant="rounded" height={180} />
              ))}
            </Box>
          ) : alarmList.length === 0 ? (
            <Box className="empty-panel">
              <NotificationsIcon className="empty-panel__icon" />
              <Typography color="text.secondary" variant="h6">
                No alarm rules
              </Typography>
              <Typography color="text.secondary" variant="body2">
                Click "New Rule" to create a detection alarm
              </Typography>
            </Box>
          ) : (
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 2 }}>
              {alarmList.map((alarm: Alarm) => {
                const stream = streams.find((s) => s.id === alarm.stream_id)
                return (
                  <Card key={alarm.id}>
                    <CardContent className="card-content">
                      <Box className="card-header">
                        <Typography variant="h6" className="card-title" noWrap>
                          {alarm.name}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          <Chip
                            icon={<CircleIcon sx={{ fontSize: '10px !important' }} />}
                            label={alarm.is_active ? 'Active' : 'Off'}
                            size="small"
                            color={alarm.is_active ? 'success' : 'default'}
                          />
                          <Chip label={alarm.severity} size="small" color={SEVERITY_COLORS[alarm.severity]} />
                        </Box>
                      </Box>
                      <Box className="card-info">
                        <Box className="card-info__row">
                          <Typography variant="body2" color="text.secondary">
                            Stream
                          </Typography>
                          <Typography variant="body2">{stream?.stream_name ?? `#${alarm.stream_id}`}</Typography>
                        </Box>
                        <Box className="card-info__row">
                          <Typography variant="body2" color="text.secondary">
                            Trigger
                          </Typography>
                          <Chip label={TRIGGER_LABELS[alarm.trigger_type]} size="small" />
                        </Box>
                        <Box className="card-info__row">
                          <Typography variant="body2" color="text.secondary">
                            Class
                          </Typography>
                          <Typography variant="body2">{alarm.trigger_config.class_names?.join(', ')}</Typography>
                        </Box>
                        <Box className="card-info__row">
                          <Typography variant="body2" color="text.secondary">
                            Hysteresis
                          </Typography>
                          <Typography variant="body2" fontSize="0.75rem">
                            ON {alarm.min_on_seconds}s / OFF {alarm.min_off_seconds}s / CD {alarm.cooldown_seconds}s
                          </Typography>
                        </Box>
                      </Box>
                      <Box className="card-actions">
                        <IconButton
                          size="small"
                          onClick={() => openAlarmDialog(alarm)}
                          className="icon-button--primary"
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                        <IconButton
                          size="small"
                          onClick={() => deleteMutation.mutate(alarm.id)}
                          className="icon-button--error"
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    </CardContent>
                  </Card>
                )
              })}
            </Box>
          )}
        </>
      )}

      {/* ── Tab 1: Events ─── */}
      {tab === 1 && (
        <>
          {eventsLoading ? (
            <Grid container spacing={2}>
              {[1, 2, 3].map((i) => (
                <Grid item xs={12} sm={6} md={4} key={i}>
                  <Skeleton variant="rounded" height={220} />
                </Grid>
              ))}
            </Grid>
          ) : eventList.length === 0 ? (
            <Box className="empty-panel">
              <OpenIcon className="empty-panel__icon" />
              <Typography color="text.secondary" variant="h6">
                No alarm events
              </Typography>
              <Typography color="text.secondary" variant="body2">
                Events appear here when alarm rules trigger
              </Typography>
            </Box>
          ) : (
            <Grid container spacing={2}>
              {eventList.map((ev) => {
                const alarm = alarmList.find((a) => a.id === ev.alarm_id)
                const stream = streams.find((s) => s.id === ev.stream_id)
                const snapshotUrl = ev.has_snapshot ? buildAlarmEventSnapshotUrl(ev.id) : null
                const classText = ev.matched_classes
                  ? Object.entries(ev.matched_classes)
                      .map(([cls, cnt]) => `${cls}×${cnt}`)
                      .join(', ') || '—'
                  : '—'
                return (
                  <Grid item xs={12} sm={6} md={4} key={ev.id}>
                    <Card variant="outlined" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                      {/* Snapshot or placeholder */}
                      {snapshotUrl ? (
                        <CardMedia
                          component="img"
                          image={snapshotUrl}
                          alt="alarm snapshot"
                          sx={{ height: 160, objectFit: 'cover', bgcolor: 'grey.900' }}
                        />
                      ) : (
                        <Box
                          sx={{
                            height: 160,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            bgcolor: 'grey.900',
                            color: 'grey.600',
                          }}
                        >
                          <NoImageIcon sx={{ fontSize: 48 }} />
                        </Box>
                      )}
                      <CardContent sx={{ flex: 1, p: 1.5, '&:last-child': { pb: 1.5 } }}>
                        {/* Header row */}
                        <Box
                          sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 0.5 }}
                        >
                          <Typography variant="subtitle2" noWrap sx={{ maxWidth: '70%' }}>
                            {alarm?.name ?? `Alarm #${ev.alarm_id}`}
                          </Typography>
                          <Chip label={ev.state} size="small" color={STATE_COLORS[ev.state]} />
                        </Box>

                        {/* Stream */}
                        <Typography variant="caption" color="text.secondary" display="block">
                          {stream?.stream_name ?? `Stream #${ev.stream_id}`}
                        </Typography>

                        <Divider sx={{ my: 0.75 }} />

                        {/* Triggered / closed times */}
                        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0.25, mb: 0.5 }}>
                          <Typography variant="caption" color="text.secondary">
                            Triggered
                          </Typography>
                          <Typography variant="caption">{fmtDate(ev.started_at)}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            Closed
                          </Typography>
                          <Typography variant="caption">{fmtDate(ev.ended_at)}</Typography>
                        </Box>

                        {/* Matched classes + confidence */}
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: '65%' }}>
                            {classText}
                          </Typography>
                          {ev.peak_confidence != null && (
                            <Chip
                              label={`${(ev.peak_confidence * 100).toFixed(0)}%`}
                              size="small"
                              variant="outlined"
                              sx={{ fontSize: '0.7rem', height: 20 }}
                            />
                          )}
                        </Box>

                        {/* Action buttons */}
                        <Box sx={{ mt: 1, display: 'flex', justifyContent: 'flex-end', gap: 0.5 }}>
                          {ev.state === 'open' && (
                            <Tooltip title="Acknowledge">
                              <IconButton
                                size="small"
                                onClick={() => ackMutation.mutate({ id: ev.id })}
                                className="icon-button--primary"
                              >
                                <AckIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                          <Tooltip title="Delete event">
                            <IconButton
                              size="small"
                              onClick={() => deleteEventMutation.mutate(ev.id)}
                              className="icon-button--error"
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                )
              })}
            </Grid>
          )}
        </>
      )}

      {/* Dialogs */}
      <AlarmDialog
        open={alarmDialogOpen}
        editing={editingAlarm}
        streams={streams}
        onClose={() => setAlarmDialogOpen(false)}
      />
    </Box>
  )
}

export default Alarms
