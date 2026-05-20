import React, { useEffect, useState } from 'react'
import {
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
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import type { ChipProps } from '@mui/material'
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  PlayCircle as PlayCircleIcon,
  Circle as CircleIcon,
} from '@mui/icons-material'
import {
  useStreams,
  useCreateStream,
  useUpdateStream,
  useDeleteStream,
  useCameras,
  useInferenceRuntimeConfig,
  useUpdateInferenceRuntimeConfig,
  useRealtimeInferenceMetrics,
  useBenchmarkScenarioTemplate,
  useExportBenchmarkMetrics,
} from '../hooks/useQueries'
import { Stream, Camera, StreamInferenceMetrics } from '../types'
import CameraStream, { CameraStreamStatsSnapshot } from '../components/CameraStream'

const inferTaskTypeFromModel = (modelName: string): string => {
  const lower = modelName.toLowerCase()
  if (lower.includes('pose')) return 'pose'
  if (lower.includes('seg')) return 'segment'
  return 'detect'
}

const TASK_OBJECTIVE_LABELS: Record<string, string> = {
  detect: 'Object Detection',
  pose: 'Pose Estimation',
  segment: 'Segmentation',
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
  const [formData, setFormData] = useState({
    camera_id: 0,
    status: 'stopped',
    current_frame: 0,
    detection_enabled: true,
    sync_video_predictions: false,
    detection_task_type: 'detect',
    stream_metadata: {},
  })
  const [runtimeForm, setRuntimeForm] = useState({
    model_name: '',
    accelerator: 'cpu',
    task_type: 'detect',
  })
  const [taskObjectiveFilter, setTaskObjectiveFilter] = useState<string>('detect')
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
  const updateRuntimeMutation = useUpdateInferenceRuntimeConfig()
  const exportBenchmarkMutation = useExportBenchmarkMetrics()

  const { data: runtimeConfig } = useInferenceRuntimeConfig()
  const { data: realtimeMetrics } = useRealtimeInferenceMetrics()
  const { data: benchmarkTemplate } = useBenchmarkScenarioTemplate()

  useEffect(() => {
    if (runtimeConfig) {
      setRuntimeForm({
        model_name: runtimeConfig.model_name,
        accelerator: runtimeConfig.accelerator,
        task_type: runtimeConfig.task_type,
      })
    }
  }, [runtimeConfig])

  const handleOpen = (stream?: Stream) => {
    const currentTaskType = runtimeConfig?.task_type || 'detect'
    setTaskObjectiveFilter(currentTaskType)
    if (stream) {
      setSelectedStream(stream)
      setFormData({
        camera_id: stream.camera_id,
        status: stream.status,
        current_frame: stream.current_frame,
        detection_enabled:
          typeof stream.detection_enabled === 'boolean'
            ? stream.detection_enabled
            : Boolean(stream.stream_metadata?.detection_enabled),
        sync_video_predictions:
          typeof stream.sync_video_predictions === 'boolean'
            ? stream.sync_video_predictions
            : Boolean(stream.stream_metadata?.sync_video_predictions),
        detection_task_type: stream.detection_task_type || stream.stream_metadata?.detection_task_type || 'detect',
        stream_metadata: stream.stream_metadata,
      })
    } else {
      setSelectedStream(null)
      setFormData({
        camera_id: 0,
        status: 'stopped',
        current_frame: 0,
        detection_enabled: true,
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
    setTaskObjectiveFilter('detect')
    setFormData({
      camera_id: 0,
      status: 'stopped',
      current_frame: 0,
      detection_enabled: true,
      sync_video_predictions: false,
      detection_task_type: 'detect',
      stream_metadata: {},
    })
  }

  const handleTaskObjectiveChange = (_: React.MouseEvent<HTMLElement>, newObjective: string | null) => {
    if (!newObjective) return
    setTaskObjectiveFilter(newObjective)
    const newFilteredModels = (runtimeConfig?.available_models || []).filter(
      (model) => inferTaskTypeFromModel(model) === newObjective,
    )
    const firstMatch = newFilteredModels[0] || runtimeForm.model_name
    setRuntimeForm({ ...runtimeForm, task_type: newObjective, model_name: firstMatch })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await updateRuntimeMutation.mutateAsync({
      model_name: runtimeForm.model_name,
      accelerator: runtimeForm.accelerator,
      task_type: runtimeForm.task_type,
    })

    const streamPayload = {
      ...formData,
      detection_model: runtimeForm.model_name,
      detection_task_type: runtimeForm.task_type,
    }

    if (selectedStream) {
      updateMutation.mutate({ id: selectedStream.id, data: streamPayload }, { onSuccess: () => handleClose() })
    } else {
      createMutation.mutate(streamPayload, { onSuccess: () => handleClose() })
    }
  }

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

  const streamList = Array.isArray(streams) ? streams : []
  const cameraList = Array.isArray(cameras) ? cameras : []

  const handleStreamStatsChange = (streamId: number, stats: CameraStreamStatsSnapshot) => {
    setStreamPreviewStats((prev) => ({ ...prev, [streamId]: stats }))
  }

  const handleExportBenchmark = async () => {
    const template =
      benchmarkTemplate ||
      ({
        scenario_name: 'baseline_default',
        duration_seconds: 300,
        stream_count: 1,
        resolution: '640x360',
        model_name: 'yolov8n.pt',
        annotation_enabled: true,
        notes: null,
      } as const)

    const activeStreams = streamList.filter((stream) => stream.status === 'active').length

    await exportBenchmarkMutation.mutateAsync({
      ...template,
      scenario_name: `frontend_snapshot_${new Date().toISOString().replace(/[:.]/g, '-')}`,
      stream_count: Math.max(activeStreams, 1),
      model_name: runtimeConfig?.model_name || template.model_name,
      notes: 'Export triggered from Streams frontend page',
    })
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
            onClick={handleExportBenchmark}
            disabled={exportBenchmarkMutation.isPending}
            className="page-header__action page-header__action--outline"
          >
            {exportBenchmarkMutation.isPending ? 'Exporting...' : 'Export Benchmark'}
          </Button>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => refetchStreams()}
            className="page-header__action page-header__action--outline"
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpen()}
            className="page-header__action"
          >
            Add Stream
          </Button>
        </Box>
      </Box>

      {exportBenchmarkMutation.isSuccess && exportBenchmarkMutation.data?.data && (
        <Alert severity="success" sx={{ mb: 2 }}>
          Benchmark exported: {exportBenchmarkMutation.data.data.run_id} (
          {exportBenchmarkMutation.data.data.streams_count} streams)
        </Alert>
      )}

      {exportBenchmarkMutation.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to export benchmark snapshot.
        </Alert>
      )}

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
            {streamList.map((stream: Stream) => {
              const camera = cameraList.find((c: Camera) => c.id === stream.camera_id)
              const performance = realtimeMetrics?.per_stream?.[stream.id]
              const configuredInferenceFps =
                performance?.target_inference_fps ??
                Number(stream.stream_metadata?.max_inference_fps ?? stream.stream_metadata?.detection_max_inference_fps)
              const configuredOutputFps =
                performance?.output_fps ?? Number(stream.stream_metadata?.output_fps ?? stream.stream_metadata?.fps)
              const detectionEnabled =
                typeof stream.detection_enabled === 'boolean'
                  ? stream.detection_enabled
                  : Boolean(stream.stream_metadata?.detection_enabled)
              const showNoWorkerBadge = detectionEnabled && !stream.worker_active
              const syncVideoPredictions =
                typeof stream.sync_video_predictions === 'boolean'
                  ? stream.sync_video_predictions
                  : Boolean(stream.stream_metadata?.sync_video_predictions)
              return (
                <Card key={stream.id}>
                  <CardContent className="card-content">
                    {/* Header */}
                    <Box className="card-header">
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
                    </Box>

                    {showNoWorkerBadge && (
                      <Chip label="No active worker" size="small" color="warning" sx={{ mt: 1, mb: 1 }} />
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

                    {/* Frame Counter */}
                    <Typography variant="body2" color="text.secondary" className="stream-frame-count">
                      Frame: {stream.current_frame.toLocaleString()}
                    </Typography>
                    <Box
                      sx={{
                        mt: 1,
                        mb: 2,
                        p: 1.5,
                        borderRadius: 2,
                        border: '1px solid',
                        borderColor: 'divider',
                        backgroundColor: 'rgba(255, 255, 255, 0.02)',
                        display: 'grid',
                        gap: 1,
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
                        <Typography variant="subtitle2">Performance</Typography>
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
                              AI inference FPS (actual)
                            </Typography>
                            <Tooltip title="Actual number of frames per second processed by the AI inference engine (after all throttling and resource limits).">
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
                              AI inference FPS (configured max)
                            </Typography>
                            <Tooltip title="Configured maximum FPS for AI inference (system will not process more than this per second, even if hardware allows).">
                              <SvgIcon fontSize="small" sx={{ cursor: 'pointer', color: 'action.active' }}>
                                <HelpOutlineIcon />
                              </SvgIcon>
                            </Tooltip>
                          </Box>
                          <Typography variant="body2">{formatMetricNumber(configuredInferenceFps)} fps</Typography>
                        </Box>
                        <Box>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <Typography variant="caption" color="text.secondary">
                              AI engine throughput (raw)
                            </Typography>
                            <Tooltip title="Raw throughput: how many frames per second the AI engine could process if not limited by the configured cap.">
                              <SvgIcon fontSize="small" sx={{ cursor: 'pointer', color: 'action.active' }}>
                                <HelpOutlineIcon />
                              </SvgIcon>
                            </Tooltip>
                          </Box>
                          <Typography variant="body2">
                            {formatMetricNumber(performance?.inference_throughput_fps)} fps
                          </Typography>
                        </Box>
                        <Box>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <Typography variant="caption" color="text.secondary">
                              Avg inference latency
                            </Typography>
                            <Tooltip title="Average time (ms) to process a single frame with the current model and hardware.">
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
                            <Tooltip title="Time (ms) taken for the most recent inference operation.">
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
                            Range
                          </Typography>
                          <Typography variant="body2">
                            {formatMetricNumber(performance?.min_inference_time_ms)}-
                            {formatMetricNumber(performance?.max_inference_time_ms)} ms
                          </Typography>
                        </Box>
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
                              Source stream FPS (actual)
                            </Typography>
                            <Tooltip title="Actual frame rate of the incoming camera/video stream as rendered in the browser.">
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
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <Typography variant="caption" color="text.secondary">
                              AI stream FPS (actual)
                            </Typography>
                            <Tooltip title="Actual frame rate of the annotated (AI overlay) stream as received by the browser.">
                              <SvgIcon fontSize="small" sx={{ cursor: 'pointer', color: 'action.active' }}>
                                <HelpOutlineIcon />
                              </SvgIcon>
                            </Tooltip>
                          </Box>
                          <Typography variant="body2">
                            {formatMetricNumber(streamPreviewStats[stream.id]?.detectionFps)} fps
                          </Typography>
                        </Box>
                        <Box>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <Typography variant="caption" color="text.secondary">
                              AI stream FPS (configured output)
                            </Typography>
                            <Tooltip title="Configured output FPS for the annotated (AI overlay) stream. This is the maximum rate at which annotated frames are published to clients.">
                              <SvgIcon fontSize="small" sx={{ cursor: 'pointer', color: 'action.active' }}>
                                <HelpOutlineIcon />
                              </SvgIcon>
                            </Tooltip>
                          </Box>
                          <Typography variant="body2">{formatMetricNumber(configuredOutputFps)} fps</Typography>
                        </Box>
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            Stream transmit speed
                          </Typography>
                          <Typography variant="body2">{streamPreviewStats[stream.id]?.throughput || '--'}</Typography>
                        </Box>
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            Stream resolution
                          </Typography>
                          <Typography variant="body2">{streamPreviewStats[stream.id]?.resolution || '--'}</Typography>
                        </Box>
                      </Box>

                      <Typography variant="body2" color="text.secondary">
                        Model: {performance?.model_name || stream.detection_model || runtimeConfig?.model_name || 'n/a'}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Accelerator: {performance?.accelerator || runtimeConfig?.accelerator || 'n/a'}
                      </Typography>
                    </Box>

                    {/* Actions */}
                    <Box className="card-actions">
                      <IconButton size="small" onClick={() => handleOpen(stream)} className="icon-button--primary">
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => deleteMutation.mutate(stream.id)}
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
      </Box>

      <Dialog open={open} onClose={handleClose}>
        <DialogTitle>{selectedStream ? 'Edit Stream' : 'Add Stream'}</DialogTitle>
        <form onSubmit={handleSubmit}>
          <DialogContent>
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

            <FormControlLabel
              control={
                <Switch
                  checked={formData.sync_video_predictions}
                  onChange={(e) => setFormData({ ...formData, sync_video_predictions: e.target.checked })}
                />
              }
              label="Sync video and predictions (backend dispatch)"
            />

            <Box sx={{ mt: 1, mb: 0.5 }}>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
                Task Objective
              </Typography>
              <ToggleButtonGroup
                value={taskObjectiveFilter}
                exclusive
                onChange={handleTaskObjectiveChange}
                size="small"
                fullWidth
              >
                {(runtimeConfig?.available_task_types || ['detect', 'pose', 'segment']).map((taskType) => (
                  <ToggleButton key={taskType} value={taskType}>
                    {TASK_OBJECTIVE_LABELS[taskType] ?? taskType}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </Box>

            <FormControl fullWidth margin="dense">
              <InputLabel>System Model</InputLabel>
              <Select
                value={runtimeForm.model_name}
                label="System Model"
                onChange={(e) => {
                  const model = e.target.value as string
                  const inferredTaskType = inferTaskTypeFromModel(model)
                  setRuntimeForm({ ...runtimeForm, model_name: model, task_type: inferredTaskType })
                  setTaskObjectiveFilter(inferredTaskType)
                }}
              >
                {(runtimeConfig?.available_models || [])
                  .filter((model) => inferTaskTypeFromModel(model) === taskObjectiveFilter)
                  .map((model) => (
                    <MenuItem key={model} value={model}>
                      {model}
                    </MenuItem>
                  ))}
              </Select>
            </FormControl>

            <FormControl fullWidth margin="dense">
              <InputLabel>System Accelerator</InputLabel>
              <Select
                value={runtimeForm.accelerator}
                label="System Accelerator"
                onChange={(e) => setRuntimeForm({ ...runtimeForm, accelerator: e.target.value })}
              >
                {(runtimeConfig?.available_accelerators || ['cpu']).map((accelerator) => (
                  <MenuItem key={accelerator} value={accelerator}>
                    {accelerator}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Typography variant="caption" color="text.secondary">
              Model, accelerator, and task type are applied globally to all streams.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleClose}>Cancel</Button>
            <Button type="submit" variant="contained">
              {selectedStream ? 'Update' : 'Create'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Box>
  )
}

export default Streams
