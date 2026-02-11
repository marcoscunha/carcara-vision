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
  TextField,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Skeleton,
} from '@mui/material'
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Notifications as NotificationsIcon,
  Circle as CircleIcon,
} from '@mui/icons-material'
import { useAlarms, useCreateAlarm, useUpdateAlarm, useDeleteAlarm, useCameras, useModels } from '../hooks/useQueries'
import { Alarm, Camera, Model } from '../types'

const Alarms: React.FC = () => {
  const [open, setOpen] = useState(false)
  const [selectedAlarm, setSelectedAlarm] = useState<Alarm | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    camera_id: 0,
    class_name: '',
    confidence_threshold: 0.5,
    region_of_interest: [0, 0, 0, 0],
    is_active: true,
  })

  // TanStack Query hooks for server state management
  const { data: alarms, isLoading: alarmsLoading } = useAlarms()
  const { data: cameras, isLoading: camerasLoading } = useCameras()
  const { data: models, isLoading: modelsLoading } = useModels()

  const createMutation = useCreateAlarm()
  const updateMutation = useUpdateAlarm()
  const deleteMutation = useDeleteAlarm()

  const handleOpen = (alarm?: Alarm) => {
    if (alarm) {
      setSelectedAlarm(alarm)
      setFormData({
        name: alarm.name,
        camera_id: alarm.camera_id,
        class_name: alarm.class_name,
        confidence_threshold: alarm.confidence_threshold,
        region_of_interest: alarm.region_of_interest,
        is_active: alarm.is_active,
      })
    } else {
      setSelectedAlarm(null)
      setFormData({
        name: '',
        camera_id: 0,
        class_name: '',
        confidence_threshold: 0.5,
        region_of_interest: [0, 0, 0, 0],
        is_active: true,
      })
    }
    setOpen(true)
  }

  const handleClose = () => {
    setOpen(false)
    setSelectedAlarm(null)
    setFormData({
      name: '',
      camera_id: 0,
      class_name: '',
      confidence_threshold: 0.5,
      region_of_interest: [0, 0, 0, 0],
      is_active: true,
    })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (selectedAlarm) {
      updateMutation.mutate({ id: selectedAlarm.id, data: formData }, { onSuccess: () => handleClose() })
    } else {
      createMutation.mutate(formData, { onSuccess: () => handleClose() })
    }
  }

  if (alarmsLoading || camerasLoading || modelsLoading) {
    return (
      <Box>
        <Box className="loading-header">
          <Skeleton variant="text" width={120} height={40} />
          <Skeleton variant="rounded" width={130} height={40} />
        </Box>
        <Box className="card-grid--alarms">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} variant="rounded" height={180} />
          ))}
        </Box>
      </Box>
    )
  }

  const alarmList = alarms?.data || []
  const cameraList = cameras?.data || []
  const modelList = models?.data || []

  return (
    <Box className="fade-in">
      {/* Page Header */}
      <Box className="page-header">
        <Box>
          <Typography variant="h4" className="page-header__title">
            Alarms
          </Typography>
          <Typography variant="body2" color="text.secondary" className="page-header__subtitle">
            Configure detection alerts and notifications
          </Typography>
        </Box>
        <Box className="page-header__actions">
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpen()}
            className="page-header__action"
          >
            Add Alarm
          </Button>
        </Box>
      </Box>

      {/* Alarms Grid */}
      <Box className="section section--compact">
        <Box className="section-header">
          <Box className="section-header__accent" />
          <Typography variant="h5" className="section-header__title">
            Configured Alarms
          </Typography>
          <Chip label={alarmList.length} size="small" className="section-header__count" />
        </Box>

        {alarmList.length === 0 ? (
          <Box className="empty-panel">
            <NotificationsIcon className="empty-panel__icon" />
            <Typography color="text.secondary" variant="h6" className="empty-panel__title">
              No alarms configured
            </Typography>
            <Typography color="text.secondary" variant="body2">
              Click "Add Alarm" to create your first detection alert
            </Typography>
          </Box>
        ) : (
          <Box className="card-grid--alarms">
            {alarmList.map((alarm: Alarm) => {
              const camera = cameraList.find((c: Camera) => c.id === alarm.camera_id)
              return (
                <Card key={alarm.id}>
                  <CardContent className="card-content">
                    {/* Header */}
                    <Box className="card-header">
                      <Typography variant="h6" className="card-title">
                        {alarm.name}
                      </Typography>
                      <Chip
                        icon={<CircleIcon className="chip-icon--tiny" />}
                        label={alarm.is_active ? 'Active' : 'Inactive'}
                        size="small"
                        color={alarm.is_active ? 'success' : 'error'}
                        className={`status-chip ${alarm.is_active ? 'status-chip--active' : ''}`}
                      />
                    </Box>

                    {/* Info Grid */}
                    <Box className="card-info">
                      <Box className="card-info__row">
                        <Typography variant="body2" color="text.secondary">
                          Camera
                        </Typography>
                        <Typography variant="body2" className="card-info__value">
                          {camera?.name || 'Unknown'}
                        </Typography>
                      </Box>
                      <Box className="card-info__row">
                        <Typography variant="body2" color="text.secondary">
                          Detection Class
                        </Typography>
                        <Chip label={alarm.class_name} size="small" className="card-chip" />
                      </Box>
                      <Box className="card-info__row">
                        <Typography variant="body2" color="text.secondary">
                          Confidence
                        </Typography>
                        <Typography variant="body2" className="card-info__value">
                          {(alarm.confidence_threshold * 100).toFixed(0)}%
                        </Typography>
                      </Box>
                    </Box>

                    {/* Actions */}
                    <Box className="card-actions">
                      <IconButton size="small" onClick={() => handleOpen(alarm)} className="icon-button--primary">
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
      </Box>

      <Dialog open={open} onClose={handleClose}>
        <DialogTitle>{selectedAlarm ? 'Edit Alarm' : 'Add Alarm'}</DialogTitle>
        <form onSubmit={handleSubmit}>
          <DialogContent>
            <TextField
              autoFocus
              margin="dense"
              label="Name"
              fullWidth
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
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
            <FormControl fullWidth margin="dense">
              <InputLabel>Model</InputLabel>
              <Select
                value={formData.class_name}
                label="Model"
                onChange={(e) => setFormData({ ...formData, class_name: e.target.value })}
              >
                {modelList.map((model: Model) => (
                  <MenuItem key={model.name} value={model.name}>
                    {model.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              margin="dense"
              label="Confidence Threshold"
              type="number"
              fullWidth
              value={formData.confidence_threshold}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  confidence_threshold: Number(e.target.value),
                })
              }
              inputProps={{ min: 0, max: 1, step: 0.1 }}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={handleClose}>Cancel</Button>
            <Button type="submit" variant="contained">
              {selectedAlarm ? 'Update' : 'Create'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Box>
  )
}

export default Alarms
