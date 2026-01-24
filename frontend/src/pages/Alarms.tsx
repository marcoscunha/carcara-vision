import React, { useState } from 'react';
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
  alpha,
  useTheme,
  Skeleton,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Notifications as NotificationsIcon,
  Circle as CircleIcon,
} from '@mui/icons-material';
import { useAlarms, useCreateAlarm, useUpdateAlarm, useDeleteAlarm, useCameras, useModels } from '../hooks/useQueries';
import { Alarm, Camera, Model } from '../types';

const Alarms: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [selectedAlarm, setSelectedAlarm] = useState<Alarm | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    camera_id: 0,
    class_name: '',
    confidence_threshold: 0.5,
    region_of_interest: [0, 0, 0, 0],
    is_active: true,
  });
  const theme = useTheme();

  // TanStack Query hooks for server state management
  const { data: alarms, isLoading: alarmsLoading } = useAlarms();
  const { data: cameras, isLoading: camerasLoading } = useCameras();
  const { data: models, isLoading: modelsLoading } = useModels();

  const createMutation = useCreateAlarm();
  const updateMutation = useUpdateAlarm();
  const deleteMutation = useDeleteAlarm();

  const handleOpen = (alarm?: Alarm) => {
    if (alarm) {
      setSelectedAlarm(alarm);
      setFormData({
        name: alarm.name,
        camera_id: alarm.camera_id,
        class_name: alarm.class_name,
        confidence_threshold: alarm.confidence_threshold,
        region_of_interest: alarm.region_of_interest,
        is_active: alarm.is_active,
      });
    } else {
      setSelectedAlarm(null);
      setFormData({
        name: '',
        camera_id: 0,
        class_name: '',
        confidence_threshold: 0.5,
        region_of_interest: [0, 0, 0, 0],
        is_active: true,
      });
    }
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
    setSelectedAlarm(null);
    setFormData({
      name: '',
      camera_id: 0,
      class_name: '',
      confidence_threshold: 0.5,
      region_of_interest: [0, 0, 0, 0],
      is_active: true,
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedAlarm) {
      updateMutation.mutate(
        { id: selectedAlarm.id, data: formData },
        { onSuccess: () => handleClose() }
      );
    } else {
      createMutation.mutate(formData, { onSuccess: () => handleClose() });
    }
  };

  if (alarmsLoading || camerasLoading || modelsLoading) {
    return (
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
          <Skeleton variant="text" width={120} height={40} />
          <Skeleton variant="rounded" width={130} height={40} />
        </Box>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 3 }}>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} variant="rounded" height={180} />
          ))}
        </Box>
      </Box>
    );
  }

  const alarmList = alarms?.data || [];
  const cameraList = cameras?.data || [];
  const modelList = models?.data || [];

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
            Alarms
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Configure detection alerts and notifications
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpen()}
          sx={{
            px: 3,
            py: 1.25,
          }}
        >
          Add Alarm
        </Button>
      </Box>

      {/* Alarms Grid */}
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
          <Typography variant="h5" sx={{ fontWeight: 600 }}>Configured Alarms</Typography>
          <Chip
            label={alarmList.length}
            size="small"
            sx={{
              ml: 1,
              backgroundColor: alpha(theme.palette.primary.main, 0.15),
              color: theme.palette.primary.main,
              fontWeight: 600,
            }}
          />
        </Box>

        {alarmList.length === 0 ? (
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
            <NotificationsIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography color="text.secondary" variant="h6" sx={{ mb: 1 }}>
              No alarms configured
            </Typography>
            <Typography color="text.secondary" variant="body2">
              Click "Add Alarm" to create your first detection alert
            </Typography>
          </Box>
        ) : (
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 3 }}>
            {alarmList.map((alarm: Alarm) => {
              const camera = cameraList.find((c: Camera) => c.id === alarm.camera_id);
              return (
                <Card key={alarm.id}>
                  <CardContent sx={{ p: 2.5 }}>
                    {/* Header */}
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>{alarm.name}</Typography>
                      <Chip
                        icon={<CircleIcon sx={{ fontSize: '10px !important' }} />}
                        label={alarm.is_active ? 'Active' : 'Inactive'}
                        size="small"
                        color={alarm.is_active ? 'success' : 'error'}
                        sx={{
                          '& .MuiChip-icon': {
                            color: 'inherit',
                            animation: alarm.is_active ? 'pulse 2s ease-in-out infinite' : 'none',
                          },
                        }}
                      />
                    </Box>

                    {/* Info Grid */}
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 2 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Camera</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>{camera?.name || 'Unknown'}</Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Detection Class</Typography>
                        <Chip
                          label={alarm.class_name}
                          size="small"
                          sx={{
                            height: 22,
                            backgroundColor: alpha(theme.palette.secondary.main, 0.15),
                            color: theme.palette.secondary.main,
                          }}
                        />
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Confidence</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {(alarm.confidence_threshold * 100).toFixed(0)}%
                        </Typography>
                      </Box>
                    </Box>

                    {/* Actions */}
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.5 }}>
                      <IconButton
                        size="small"
                        onClick={() => handleOpen(alarm)}
                        sx={{
                          color: 'primary.main',
                          '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.12) },
                        }}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => deleteMutation.mutate(alarm.id)}
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
              );
            })}
          </Box>
        )}
      </Box>

      <Dialog open={open} onClose={handleClose}>
        <DialogTitle>
          {selectedAlarm ? 'Edit Alarm' : 'Add Alarm'}
        </DialogTitle>
        <form onSubmit={handleSubmit}>
          <DialogContent>
            <TextField
              autoFocus
              margin="dense"
              label="Name"
              fullWidth
              value={formData.name}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
            />
            <FormControl fullWidth margin="dense">
              <InputLabel>Camera</InputLabel>
              <Select
                value={formData.camera_id}
                label="Camera"
                onChange={(e) =>
                  setFormData({ ...formData, camera_id: Number(e.target.value) })
                }
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
                onChange={(e) =>
                  setFormData({ ...formData, class_name: e.target.value })
                }
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
  );
};

export default Alarms;