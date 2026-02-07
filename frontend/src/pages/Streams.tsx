import React, { useState } from 'react'
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
  alpha,
  useTheme,
} from '@mui/material'
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  PlayCircle as PlayCircleIcon,
  Circle as CircleIcon,
} from '@mui/icons-material'
import { useStreams, useCreateStream, useUpdateStream, useDeleteStream, useCameras } from '../hooks/useQueries'
import { Stream, Camera } from '../types'
import CameraStream from '../components/CameraStream'

const Streams: React.FC = () => {
  const [open, setOpen] = useState(false)
  const [selectedStream, setSelectedStream] = useState<Stream | null>(null)
  const [formData, setFormData] = useState({
    camera_id: 0,
    status: 'stopped',
    current_frame: 0,
    stream_metadata: {},
  })
  const theme = useTheme()

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

  const handleOpen = (stream?: Stream) => {
    if (stream) {
      setSelectedStream(stream)
      setFormData({
        camera_id: stream.camera_id,
        status: stream.status,
        current_frame: stream.current_frame,
        stream_metadata: stream.stream_metadata,
      })
    } else {
      setSelectedStream(null)
      setFormData({
        camera_id: 0,
        status: 'stopped',
        current_frame: 0,
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
      stream_metadata: {},
    })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (selectedStream) {
      updateMutation.mutate({ id: selectedStream.id, data: formData }, { onSuccess: () => handleClose() })
    } else {
      createMutation.mutate(formData, { onSuccess: () => handleClose() })
    }
  }

  if (streamsLoading || camerasLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress sx={{ color: 'primary.main' }} />
      </Box>
    )
  }

  if (streamsError || camerasError) {
    return (
      <Alert
        severity="error"
        sx={{
          m: 2,
          backgroundColor: alpha(theme.palette.error.main, 0.1),
          border: `1px solid ${alpha(theme.palette.error.main, 0.3)}`,
        }}
      >
        Error loading data: {streamsErrorData?.message || 'Unknown error'}
      </Alert>
    )
  }

  const streamList = Array.isArray(streams) ? streams : []
  const cameraList = Array.isArray(cameras) ? cameras : []

  const getStatusColor = (status: string) => {
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
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 4,
          pb: 2,
          borderBottom: `1px solid ${alpha(theme.palette.divider, 0.5)}`,
        }}
      >
        <Box>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 700,
              background: `linear-gradient(135deg, ${theme.palette.text.primary} 0%, ${theme.palette.secondary.main} 100%)`,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Streams
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Monitor active video streams
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => refetchStreams()} sx={{ px: 2.5 }}>
            Refresh
          </Button>
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => handleOpen()} sx={{ px: 3 }}>
            Add Stream
          </Button>
        </Box>
      </Box>

      {/* Streams Section */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
          <Box
            sx={{
              width: 4,
              height: 24,
              borderRadius: 2,
              background: `linear-gradient(180deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
            }}
          />
          <Typography variant="h5" sx={{ fontWeight: 600 }}>
            Active Streams
          </Typography>
          <Chip
            label={streamList.length}
            size="small"
            sx={{
              ml: 1,
              backgroundColor: alpha(theme.palette.primary.main, 0.15),
              color: theme.palette.primary.main,
              fontWeight: 600,
            }}
          />
        </Box>

        {streamList.length === 0 ? (
          <Box
            sx={{
              textAlign: 'center',
              py: 6,
              px: 2,
              borderRadius: 3,
              border: `1px dashed ${alpha(theme.palette.divider, 0.5)}`,
              backgroundColor: alpha(theme.palette.background.paper, 0.3),
            }}
          >
            <PlayCircleIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography color="text.secondary" variant="h6" sx={{ mb: 1 }}>
              No active streams
            </Typography>
            <Typography color="text.secondary" variant="body2">
              Click "Add Stream" to start streaming from a camera
            </Typography>
          </Box>
        ) : (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
              gap: 3,
            }}
          >
            {streamList.map((stream: Stream) => {
              const camera = cameraList.find((c: Camera) => c.id === stream.camera_id)
              return (
                <Card key={stream.id}>
                  <CardContent sx={{ p: 2.5 }}>
                    {/* Header */}
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        mb: 2,
                      }}
                    >
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        {camera?.name || 'Unknown Camera'}
                      </Typography>
                      <Chip
                        icon={<CircleIcon sx={{ fontSize: '10px !important' }} />}
                        label={stream.status}
                        size="small"
                        color={getStatusColor(stream.status) as any}
                        sx={{
                          textTransform: 'capitalize',
                          '& .MuiChip-icon': {
                            color: 'inherit',
                            animation: stream.status === 'running' ? 'pulse 2s ease-in-out infinite' : 'none',
                          },
                        }}
                      />
                    </Box>

                    {/* Stream Preview */}
                    <Box sx={{ mb: 2 }}>
                      <CameraStream stream={stream} />
                    </Box>

                    {/* Frame Counter */}
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      Frame: {stream.current_frame.toLocaleString()}
                    </Typography>

                    {/* Actions */}
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.5 }}>
                      <IconButton
                        size="small"
                        onClick={() => handleOpen(stream)}
                        sx={{
                          color: 'primary.main',
                          '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.12) },
                        }}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => deleteMutation.mutate(stream.id)}
                        sx={{
                          color: 'error.main',
                          '&:hover': { backgroundColor: alpha(theme.palette.error.main, 0.12) },
                        }}
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
