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
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
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
    return <Typography>Loading...</Typography>;
  }

  const alarmList = alarms?.data || [];
  const cameraList = cameras?.data || [];
  const modelList = models?.data || [];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4">Alarms</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpen()}
        >
          Add Alarm
        </Button>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 3 }}>
        {alarmList.map((alarm: Alarm) => {
          const camera = cameraList.find((c: Camera) => c.id === alarm.camera_id);
          return (
            <Box key={alarm.id}>
              <Card>
                <CardContent>
                  <Typography variant="h6">{alarm.name}</Typography>
                  <Typography color="textSecondary" gutterBottom>
                    Camera: {camera?.name || 'Unknown'}
                  </Typography>
                  <Typography color="textSecondary" gutterBottom>
                    Class: {alarm.class_name}
                  </Typography>
                  <Typography color="textSecondary" gutterBottom>
                    Confidence: {alarm.confidence_threshold}
                  </Typography>
                  <Typography
                    color={alarm.is_active ? 'success.main' : 'error.main'}
                  >
                    {alarm.is_active ? 'Active' : 'Inactive'}
                  </Typography>
                  <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
                    <IconButton
                      color="primary"
                      onClick={() => handleOpen(alarm)}
                    >
                      <EditIcon />
                    </IconButton>
                    <IconButton
                      color="error"
                      onClick={() => deleteMutation.mutate(alarm.id)}
                    >
                      <DeleteIcon />
                    </IconButton>
                  </Box>
                </CardContent>
              </Card>
            </Box>
          );
        })}
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