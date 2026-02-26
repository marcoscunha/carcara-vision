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
} from '@mui/material'
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
} from '../hooks/useQueries'
import { Stream, Camera } from '../types'
import CameraStream from '../components/CameraStream'

const Streams: React.FC = () => {
  const [open, setOpen] = useState(false)
  const [selectedStream, setSelectedStream] = useState<Stream | null>(null)
  const [formData, setFormData] = useState({
    camera_id: 0,
    status: 'stopped',
    current_frame: 0,
    detection_enabled: true,
    detection_task_type: 'detect',
    stream_metadata: {},
  })
  const [runtimeForm, setRuntimeForm] = useState({
    model_name: '',
    accelerator: 'cpu',
    task_type: 'detect',
  })

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

  const { data: runtimeConfig } = useInferenceRuntimeConfig()
  const { data: realtimeMetrics } = useRealtimeInferenceMetrics()

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
        detection_task_type: 'detect',
        stream_metadata: {},
      })
    }
    setOpen(true)
  }

  const handleClose = () => {
    setOpen(false)
    setSelectedStream(null)
    setFormData({
      camera_id: 0,
      status: 'stopped',
      current_frame: 0,
      detection_enabled: true,
      detection_task_type: 'detect',
      stream_metadata: {},
    })
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
              const detectionEnabled =
                typeof stream.detection_enabled === 'boolean'
                  ? stream.detection_enabled
                  : Boolean(stream.stream_metadata?.detection_enabled)
              const showNoWorkerBadge = detectionEnabled && !stream.worker_active
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
                      <CameraStream stream={stream} />
                    </Box>

                    {/* Frame Counter */}
                    <Typography variant="body2" color="text.secondary" className="stream-frame-count">
                      Frame: {stream.current_frame.toLocaleString()}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" className="stream-frame-count">
                      Model:{' '}
                      {realtimeMetrics?.per_stream?.[stream.id]?.model_name || runtimeConfig?.model_name || 'n/a'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" className="stream-frame-count">
                      Accelerator:{' '}
                      {realtimeMetrics?.per_stream?.[stream.id]?.accelerator || runtimeConfig?.accelerator || 'n/a'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" className="stream-frame-count">
                      Inference: {realtimeMetrics?.per_stream?.[stream.id]?.avg_inference_time_ms || 0} ms • FPS:{' '}
                      {realtimeMetrics?.per_stream?.[stream.id]?.fps || 0}
                    </Typography>

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
              label="Detection Enabled"
            />

            <FormControl fullWidth margin="dense">
              <InputLabel>System Model</InputLabel>
              <Select
                value={runtimeForm.model_name}
                label="System Model"
                onChange={(e) => setRuntimeForm({ ...runtimeForm, model_name: e.target.value })}
              >
                {(runtimeConfig?.available_models || []).map((model) => (
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

            <FormControl fullWidth margin="dense">
              <InputLabel>System Task Type</InputLabel>
              <Select
                value={runtimeForm.task_type}
                label="System Task Type"
                onChange={(e) => setRuntimeForm({ ...runtimeForm, task_type: e.target.value })}
              >
                {(runtimeConfig?.available_task_types || ['detect', 'pose', 'segment']).map((taskType) => (
                  <MenuItem key={taskType} value={taskType}>
                    {taskType}
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
