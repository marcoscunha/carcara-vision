import React, { useState } from 'react'
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  Chip,
  FormControlLabel,
  Switch,
  Tooltip,
  SvgIcon,
} from '@mui/material'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import type { ChipProps } from '@mui/material'
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  ExpandMore as ExpandMoreIcon,
  Refresh as RefreshIcon,
  PlayCircle as PlayCircleIcon,
  Circle as CircleIcon,
  DragIndicator as DragIndicatorIcon,
  SwapVert as SwapVertIcon,
  Check as CheckIcon,
  WarningAmber as WarningAmberIcon,
} from '@mui/icons-material'
import {
  useStreams,
  useCreateStream,
  useUpdateStream,
  useDeleteStream,
  useReorderStreams,
  useCameras,
  useModels,
  useInferenceRuntimeConfig,
  useRealtimeInferenceMetrics,
} from '../hooks/useQueries'
import { Stream, Camera, StreamInferenceMetrics, Model } from '../types'
import CameraStream, { CameraStreamStatsSnapshot } from '../components/CameraStream'

const inferTaskTypeFromModel = (modelName: string): string => {
  const lower = modelName.toLowerCase()
  if (lower.includes('pose')) return 'pose'
  if (lower.includes('seg')) return 'segment'
  return 'detect'
}

const formatMetricNumber = (value: number | null | undefined, digits = 1): string => {
  if (typeof value !== 'number' || Number.isNaN(value) || value <= 0) {
    return '--'
  }

  return value.toFixed(digits)
}

const getPerformanceTone = (metrics?: StreamInferenceMetrics): 'success' | 'warning' | 'default' => {
  if (!metrics || metrics.samples === 0) {
    return 'default'
  }

  if (metrics.avg_inference_time_ms <= 40) {
    return 'success'
  }

  return 'warning'
}

const Streams: React.FC = () => {
  const [open, setOpen] = useState(false)
  const [selectedStream, setSelectedStream] = useState<Stream | null>(null)
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create')
  const [formData, setFormData] = useState({
    camera_id: 0,
    status: 'stopped',
    current_frame: 0,
    detection_enabled: true,
    detection_model: '',
    sync_video_predictions: false,
    detection_task_type: 'detect',
    stream_metadata: {},
  })
  const [streamPreviewStats, setStreamPreviewStats] = useState<Record<number, CameraStreamStatsSnapshot>>({})

  // TanStack Query hooks for server state management
  const {
    data: streams,
    isLoading: streamsLoading,
    isError: streamsError,
    error: streamsErrorData,
    refetch: refetchStreams,
  } = useStreams()

  const { data: cameras, isLoading: camerasLoading, isError: camerasError } = useCameras()

  const createMutation = useCreateStream()
  const updateMutation = useUpdateStream()
  const deleteMutation = useDeleteStream()
  const reorderMutation = useReorderStreams()

  const [reorderMode, setReorderMode] = useState(false)
  const [localOrder, setLocalOrder] = useState<number[] | null>(null)
  const [dragId, setDragId] = useState<number | null>(null)
  const [dragOverId, setDragOverId] = useState<number | null>(null)

  const { data: runtimeConfig } = useInferenceRuntimeConfig()
  const { data: models } = useModels()
  const { data: realtimeMetrics } = useRealtimeInferenceMetrics()
  const modelOptions = models || []
  const selectableModelOptions = modelOptions.filter((model: Model) => model.is_downloaded && model.is_enabled)
  const runtimeFallback = runtimeConfig?.model_name
  const fallbackModel =
    runtimeFallback && selectableModelOptions.some((m) => m.name === runtimeFallback)
      ? runtimeFallback
      : selectableModelOptions[0]?.name || ''
  const modelByName = new Map(modelOptions.map((model) => [model.name, model]))

  const handleOpen = (stream?: Stream) => {
    if (stream) {
      setSelectedStream(stream)
      setDialogMode('edit')
      const streamModel = stream.detection_model || stream.stream_metadata?.detection_model
      setFormData({
        camera_id: stream.camera_id,
        status: stream.status,
        current_frame: stream.current_frame,
        detection_enabled:
          typeof stream.detection_enabled === 'boolean'
            ? stream.detection_enabled
            : Boolean(stream.stream_metadata?.detection_enabled),
        detection_model:
          streamModel && selectableModelOptions.some((m) => m.name === streamModel) ? streamModel : streamModel || '',
        sync_video_predictions:
          typeof stream.sync_video_predictions === 'boolean'
            ? stream.sync_video_predictions
            : Boolean(stream.stream_metadata?.sync_video_predictions),
        detection_task_type: stream.detection_task_type || stream.stream_metadata?.detection_task_type || 'detect',
        stream_metadata: stream.stream_metadata,
      })
    } else {
      setSelectedStream(null)
      setDialogMode('create')
      setFormData({
        camera_id: 0,
        status: 'stopped',
        current_frame: 0,
        detection_enabled: true,
        detection_model: fallbackModel || '',
        sync_video_predictions: false,
        detection_task_type: 'detect',
        stream_metadata: {},
      })
    }
    setOpen(true)
  }

  const handleClose = () => {
    setOpen(false)
    setSelectedStream(null)
    setDialogMode('create')
    setFormData({
      camera_id: 0,
      status: 'stopped',
      current_frame: 0,
      detection_enabled: true,
      detection_model: fallbackModel || '',
      sync_video_predictions: false,
      detection_task_type: 'detect',
      stream_metadata: {},
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const selectedModel = formData.detection_model
    if (formData.detection_enabled && !selectedModel) {
      return
    }
    const selectedTaskType =
      modelOptions.find((m: Model) => m.name === selectedModel)?.task_type || inferTaskTypeFromModel(selectedModel)

    const streamPayload = {
      ...formData,
      detection_model: selectedModel,
      detection_task_type: selectedTaskType,
    }

    if (selectedStream) {
      updateMutation.mutate({ id: selectedStream.id, data: streamPayload }, { onSuccess: () => handleClose() })
    } else {
      createMutation.mutate(streamPayload, { onSuccess: () => handleClose() })
    }
  }

  const isSavingStream = updateMutation.isPending || createMutation.isPending
  const submitLabel = isSavingStream
    ? selectedStream || dialogMode === 'edit'
      ? 'Saving...'
      : 'Creating...'
    : selectedStream || dialogMode === 'edit'
      ? 'Save changes'
      : 'Create stream'

  if (streamsLoading || camerasLoading) {
    return (
      <Box className="loading-center">
        <CircularProgress color="primary" />
      </Box>
    )
  }

  if (streamsError || camerasError) {
    return (
      <Alert severity="error" className="alert-error">
        Error loading data: {streamsErrorData?.message || 'Unknown error'}
      </Alert>
    )
  }

  const streamList = (Array.isArray(streams) ? [...streams] : []).sort((a: Stream, b: Stream) => {
    const ao = a.display_order ?? a.id
    const bo = b.display_order ?? b.id
    if (ao !== bo) return ao - bo
    return a.id - b.id
  })

  const orderedStreamList: Stream[] = (() => {
    if (!localOrder) return streamList
    const byId = new Map(streamList.map((s) => [s.id, s]))
    const ordered = localOrder.map((id) => byId.get(id)).filter((s): s is Stream => Boolean(s))
    // Append any streams that arrived after reordering started.
    streamList.forEach((s) => {
      if (!localOrder.includes(s.id)) ordered.push(s)
    })
    return ordered
  })()

  const handleToggleReorder = () => {
    if (reorderMode) {
      setLocalOrder(null)
    } else {
      setLocalOrder(streamList.map((s) => s.id))
    }
    setReorderMode(!reorderMode)
    setDragId(null)
    setDragOverId(null)
  }

  const handleSaveOrder = async () => {
    if (!localOrder) {
      setReorderMode(false)
      return
    }
    try {
      await reorderMutation.mutateAsync(localOrder)
      setLocalOrder(null)
      setReorderMode(false)
    } catch (err) {
      console.error('Failed to save stream order', err)
    }
  }

  const handleDragStart = (e: React.DragEvent, id: number) => {
    setDragId(id)
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(id))
  }

  const handleDragOver = (e: React.DragEvent, overId: number) => {
    if (!reorderMode || dragId === null || dragId === overId) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDragOverId(overId)
  }

  const handleDrop = (e: React.DragEvent, overId: number) => {
    e.preventDefault()
    if (!reorderMode || dragId === null || dragId === overId) return
    setLocalOrder((current) => {
      const base = current ?? streamList.map((s) => s.id)
      const from = base.indexOf(dragId)
      const to = base.indexOf(overId)
      if (from === -1 || to === -1 || from === to) return base
      const next = [...base]
      next.splice(from, 1)
      next.splice(to, 0, dragId)
      return next
    })
    setDragId(null)
    setDragOverId(null)
  }

  const handleDragEnd = () => {
    setDragId(null)
    setDragOverId(null)
  }
  const cameraList = Array.isArray(cameras) ? cameras : []

  const handleStreamStatsChange = (streamId: number, stats: CameraStreamStatsSnapshot) => {
    setStreamPreviewStats((prev) => ({ ...prev, [streamId]: stats }))
  }

  const getStatusColor = (status: string): ChipProps['color'] => {
    switch (status) {
      case 'running':
        return 'success'
      case 'stopped':
        return 'error'
      default:
        return 'warning'
    }
  }

  return (
    <Box className="fade-in">
      {/* Page Header */}
      <Box className="page-header">
        <Box>
          <Typography variant="h4" className="page-header__title">
            Streams
          </Typography>
          <Typography variant="body2" color="text.secondary" className="page-header__subtitle">
            Monitor active video streams
          </Typography>
        </Box>
        <Box className="page-header__actions">
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => refetchStreams()}
            className="page-header__action page-header__action--outline"
            disabled={reorderMode}
          >
            Refresh
          </Button>
          {streamList.length > 1 &&
            (reorderMode ? (
              <>
                <Button
                  variant="outlined"
                  onClick={handleToggleReorder}
                  className="page-header__action page-header__action--outline"
                  disabled={reorderMutation.isPending}
                >
                  Cancel
                </Button>
                <Button
                  variant="contained"
                  color="success"
                  startIcon={<CheckIcon />}
                  onClick={handleSaveOrder}
                  className="page-header__action"
                  disabled={reorderMutation.isPending}
                >
                  {reorderMutation.isPending ? 'Saving…' : 'Save order'}
                </Button>
              </>
            ) : (
              <Button
                variant="outlined"
                startIcon={<SwapVertIcon />}
                onClick={handleToggleReorder}
                className="page-header__action page-header__action--outline"
              >
                Edit positions
              </Button>
            ))}
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpen()}
            className="page-header__action"
            disabled={reorderMode}
          >
            Add Stream
          </Button>
        </Box>
      </Box>

      {/* Streams Section */}
      <Box className="section section--compact">
        <Box className="section-header">
          <Box className="section-header__accent" />
          <Typography variant="h5" className="section-header__title">
            Active Streams
          </Typography>
          <Chip label={streamList.length} size="small" className="section-header__count" />
        </Box>

        {streamList.length === 0 ? (
          <Box className="empty-panel">
            <PlayCircleIcon className="empty-panel__icon" />
            <Typography color="text.secondary" variant="h6" className="empty-panel__title">
              No active streams
            </Typography>
            <Typography color="text.secondary" variant="body2">
              Click "Add Stream" to start streaming from a camera
            </Typography>
          </Box>
        ) : (
          <Box className="card-grid--streams">
            {orderedStreamList.map((stream: Stream) => {
              const camera = cameraList.find((c: Camera) => c.id === stream.camera_id)
              const performance = realtimeMetrics?.per_stream?.[stream.id]
              const detectionEnabled =
                typeof stream.detection_enabled === 'boolean'
                  ? stream.detection_enabled
                  : Boolean(stream.stream_metadata?.detection_enabled)
              const showNoWorkerBadge = detectionEnabled && !stream.worker_active
              const configuredModel = stream.detection_model || stream.stream_metadata?.detection_model || ''
              const configuredModelInfo = configuredModel ? modelByName.get(configuredModel) : undefined
              const hasModelMismatch =
                detectionEnabled &&
                Boolean(configuredModel) &&
                (!configuredModelInfo || !configuredModelInfo.is_downloaded)
              const syncVideoPredictions =
                typeof stream.sync_video_predictions === 'boolean'
                  ? stream.sync_video_predictions
                  : Boolean(stream.stream_metadata?.sync_video_predictions)
              return (
                <Card
                  key={stream.id}
                  draggable={reorderMode}
                  onDragStart={reorderMode ? (e) => handleDragStart(e, stream.id) : undefined}
                  onDragOver={reorderMode ? (e) => handleDragOver(e, stream.id) : undefined}
                  onDrop={reorderMode ? (e) => handleDrop(e, stream.id) : undefined}
                  onDragEnd={reorderMode ? handleDragEnd : undefined}
                  sx={
                    reorderMode
                      ? {
                          cursor: 'grab',
                          outline: '2px dashed',
                          outlineColor: dragOverId === stream.id ? 'primary.main' : 'transparent',
                          opacity: dragId === stream.id ? 0.5 : 1,
                          transition: 'outline-color 100ms ease, opacity 100ms ease',
                        }
                      : undefined
                  }
                >
                  <CardContent className="card-content">
                    {/* Header */}
                    <Box className="card-header">
                      {reorderMode && (
                        <DragIndicatorIcon fontSize="small" sx={{ color: 'text.secondary', mr: 0.5, cursor: 'grab' }} />
                      )}
                      <Typography variant="h6" className="card-title">
                        {camera?.name || 'Unknown Camera'}
                      </Typography>
                      <Chip
                        icon={<CircleIcon className="chip-icon--tiny" />}
                        label={stream.status}
                        size="small"
                        color={getStatusColor(stream.status)}
                        className={`status-chip chip-capitalize ${stream.status === 'running' ? 'status-chip--active' : ''}`}
                      />
                      {hasModelMismatch && (
                        <Tooltip title="Configured model is unavailable locally. Video remains visible but AI is paused.">
                          <Chip
                            icon={<WarningAmberIcon />}
                            label="Mismatch model"
                            size="small"
                            color="warning"
                            variant="outlined"
                          />
                        </Tooltip>
                      )}
                    </Box>

                    {showNoWorkerBadge && (
                      <Tooltip
                        title={
                          hasModelMismatch
                            ? 'AI is enabled but the selected model is unavailable locally.'
                            : 'AI worker is not running for this stream.'
                        }
                      >
                        <Chip label="No active worker" size="small" color="warning" sx={{ mt: 1, mb: 1 }} />
                      </Tooltip>
                    )}

                    {/* Stream Preview */}
                    <Box className="stream-preview-wrapper">
                      <CameraStream
                        stream={stream}
                        showAnnotatedStream={syncVideoPredictions}
                        showStats={false}
                        onStatsChange={(stats) => handleStreamStatsChange(stream.id, stats)}
                      />
                    </Box>

                    <Accordion
                      disableGutters
                      elevation={0}
                      sx={{
                        mt: 1,
                        mb: 2,
                        border: '1px solid',
                        borderColor: 'divider',
                        borderRadius: 2,
                        backgroundColor: 'rgba(255, 255, 255, 0.02)',
                        '&:before': { display: 'none' },
                      }}
                    >
                      <AccordionSummary
                        expandIcon={<ExpandMoreIcon />}
                        sx={{ minHeight: 40, '& .MuiAccordionSummary-content': { my: 0.5 } }}
                      >
                        <Typography variant="subtitle2">Performance</Typography>
                      </AccordionSummary>
                      <AccordionDetails sx={{ pt: 0 }}>
                        <Box
                          sx={{
                            display: 'grid',
                            gap: 1,
                          }}
                        >
                          <Box sx={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 1 }}>
                            <Chip
                              size="small"
                              label={
                                performance?.samples
                                  ? `${performance.samples} sample${performance.samples === 1 ? '' : 's'}`
                                  : 'Waiting for samples'
                              }
                              color={getPerformanceTone(performance)}
                              variant={performance?.samples ? 'filled' : 'outlined'}
                            />
                          </Box>

                          <Box
                            sx={{
                              display: 'grid',
                              gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                              gap: 1,
                            }}
                          >
                            <Box>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Typography variant="caption" color="text.secondary">
                                  AI inference FPS
                                </Typography>
                                <Tooltip title="AI frames processed per second for this stream.">
                                  <SvgIcon fontSize="small" sx={{ cursor: 'pointer', color: 'action.active' }}>
                                    <HelpOutlineIcon />
                                  </SvgIcon>
                                </Tooltip>
                              </Box>
                              <Typography variant="body2">{formatMetricNumber(performance?.fps)} fps</Typography>
                            </Box>
                            <Box>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Typography variant="caption" color="text.secondary">
                                  Avg inference latency
                                </Typography>
                                <Tooltip title="Average inference time per frame in milliseconds.">
                                  <SvgIcon fontSize="small" sx={{ cursor: 'pointer', color: 'action.active' }}>
                                    <HelpOutlineIcon />
                                  </SvgIcon>
                                </Tooltip>
                              </Box>
                              <Typography variant="body2">
                                {formatMetricNumber(performance?.avg_inference_time_ms)} ms
                              </Typography>
                            </Box>
                            <Box>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Typography variant="caption" color="text.secondary">
                                  Last inference latency
                                </Typography>
                                <Tooltip title="Most recent inference time in milliseconds.">
                                  <SvgIcon fontSize="small" sx={{ cursor: 'pointer', color: 'action.active' }}>
                                    <HelpOutlineIcon />
                                  </SvgIcon>
                                </Tooltip>
                              </Box>
                              <Typography variant="body2">
                                {formatMetricNumber(performance?.last_inference_time_ms)} ms
                              </Typography>
                            </Box>
                            <Box>
                              <Typography variant="caption" color="text.secondary">
                                Latency range
                              </Typography>
                              <Typography variant="body2">
                                {formatMetricNumber(performance?.min_inference_time_ms)}-
                                {formatMetricNumber(performance?.max_inference_time_ms)} ms
                              </Typography>
                            </Box>
                            <Box>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Typography variant="caption" color="text.secondary">
                                  Source stream FPS
                                </Typography>
                                <Tooltip title="Incoming stream frame rate in the browser preview.">
                                  <SvgIcon fontSize="small" sx={{ cursor: 'pointer', color: 'action.active' }}>
                                    <HelpOutlineIcon />
                                  </SvgIcon>
                                </Tooltip>
                              </Box>
                              <Typography variant="body2">
                                {formatMetricNumber(streamPreviewStats[stream.id]?.fps)} fps
                              </Typography>
                            </Box>
                            <Box>
                              <Typography variant="caption" color="text.secondary">
                                Resolution
                              </Typography>
                              <Typography variant="body2">
                                {streamPreviewStats[stream.id]?.resolution || '--'}
                              </Typography>
                            </Box>
                          </Box>

                          <Typography variant="body2" color="text.secondary">
                            Model:{' '}
                            {performance?.model_name || stream.detection_model || runtimeConfig?.model_name || 'n/a'}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            Accelerator: {performance?.accelerator || runtimeConfig?.accelerator || 'n/a'}
                          </Typography>
                        </Box>
                      </AccordionDetails>
                    </Accordion>

                    {/* Actions */}
                    <Box className="card-actions">
                      <Tooltip title="Edit stream settings.">
                        <span>
                          <IconButton
                            size="small"
                            onClick={() => handleOpen(stream)}
                            className="icon-button--primary"
                            disabled={reorderMode}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Delete this stream.">
                        <span>
                          <IconButton
                            size="small"
                            onClick={() => deleteMutation.mutate(stream.id)}
                            className="icon-button--error"
                            disabled={reorderMode}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </Box>
                  </CardContent>
                </Card>
              )
            })}
          </Box>
        )}
      </Box>

      <Dialog open={open} onClose={handleClose}>
        <DialogTitle>{selectedStream || dialogMode === 'edit' ? 'Edit Stream' : 'Add Stream'}</DialogTitle>
        <form onSubmit={handleSubmit}>
          <DialogContent>
            {isSavingStream && <CircularProgress size={20} sx={{ mb: 1 }} />}
            <FormControl fullWidth margin="dense">
              <InputLabel>Camera</InputLabel>
              <Select
                value={formData.camera_id}
                label="Camera"
                onChange={(e) => setFormData({ ...formData, camera_id: Number(e.target.value) })}
              >
                {cameraList.map((camera: Camera) => (
                  <MenuItem key={camera.id} value={camera.id}>
                    {camera.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControlLabel
              control={
                <Switch
                  checked={formData.detection_enabled}
                  onChange={(e) => setFormData({ ...formData, detection_enabled: e.target.checked })}
                />
              }
              label="AI Enable"
            />

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.5 }}>
              <Typography variant="body2" color="text.secondary">
                Detection model
              </Typography>
              <Tooltip title="Only downloaded active models are selectable. Unavailable assigned models appear as mismatch.">
                <HelpOutlineIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              </Tooltip>
            </Box>

            <FormControl
              fullWidth
              margin="dense"
              disabled={!formData.detection_enabled || selectableModelOptions.length === 0}
            >
              <Select
                value={formData.detection_model || ''}
                displayEmpty
                onChange={(e) => {
                  const modelName = String(e.target.value)
                  setFormData({
                    ...formData,
                    detection_model: modelName,
                    detection_task_type: inferTaskTypeFromModel(modelName),
                  })
                }}
              >
                {selectableModelOptions.length === 0 && (
                  <MenuItem value="" disabled>
                    No downloaded active models
                  </MenuItem>
                )}
                {formData.detection_model &&
                  !selectableModelOptions.some((model) => model.name === formData.detection_model) && (
                    <MenuItem value={formData.detection_model} disabled>
                      {formData.detection_model} (mismatch model)
                    </MenuItem>
                  )}
                {selectableModelOptions.map((model: Model) => (
                  <MenuItem key={model.name} value={model.name}>
                    {model.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {formData.detection_enabled && selectableModelOptions.length === 0 && (
              <Typography variant="caption" color="warning.main" sx={{ display: 'block' }}>
                No downloaded active models available. Open Settings and enable at least one downloaded model.
              </Typography>
            )}

            {formData.detection_enabled &&
              formData.detection_model &&
              !selectableModelOptions.some((model) => model.name === formData.detection_model) && (
                <Typography variant="caption" color="warning.main" sx={{ display: 'block', mt: 0.5 }}>
                  Mismatch model selected. AI remains paused until this model is available and active.
                </Typography>
              )}

            <FormControlLabel
              control={
                <Switch
                  checked={formData.sync_video_predictions}
                  onChange={(e) => setFormData({ ...formData, sync_video_predictions: e.target.checked })}
                />
              }
              label="Sync video and predictions (backend dispatch)"
            />

            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              Each stream can use a different model. Streams with the same model are eligible for paired batch
              execution.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleClose} disabled={isSavingStream}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="contained"
              disabled={isSavingStream || (formData.detection_enabled && !formData.detection_model)}
              startIcon={isSavingStream ? <CircularProgress size={14} color="inherit" /> : undefined}
            >
              {submitLabel}
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Box>
  )
}

export default Streams
