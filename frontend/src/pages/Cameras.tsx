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
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { useCameras, useCreateCamera, useUpdateCamera, useDeleteCamera } from '../hooks/useQueries';
import { Camera } from '../types';
import { CameraScanner } from '../components/CameraScanner';

const Cameras: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    rtsp_url: '',
    is_active: true,
    device_id: 0,
    resolution: [0, 0] as [number, number],
    fps: 0,
    is_available: false,
  });

  // TanStack Query hooks for server state management
  const { data: cameras, isLoading } = useCameras();

  const createMutation = useCreateCamera();
  const updateMutation = useUpdateCamera();
  const deleteMutation = useDeleteCamera();

  const handleOpen = (camera?: Camera) => {
    if (camera) {
      setSelectedCamera(camera);
      setFormData({
        name: camera.name,
        rtsp_url: camera.rtsp_url,
        is_active: camera.is_active,
        device_id: camera.device_id,
        resolution: camera.resolution,
        fps: camera.fps,
        is_available: camera.is_available,
      });
    } else {
      setSelectedCamera(null);
      setFormData({
        name: '',
        rtsp_url: '',
        is_active: true,
        device_id: 0,
        resolution: [0, 0],
        fps: 0,
        is_available: false,
      });
    }
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
    setSelectedCamera(null);
    setFormData({
      name: '',
      rtsp_url: '',
      is_active: true,
      device_id: 0,
      resolution: [0, 0],
      fps: 0,
      is_available: false,
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedCamera) {
      updateMutation.mutate(
        { id: selectedCamera.id, data: formData },
        { onSuccess: () => handleClose() }
      );
    } else {
      createMutation.mutate(formData, { onSuccess: () => handleClose() });
    }
  };

  if (isLoading) {
    return <Typography>Loading...</Typography>;
  }

  const cameraList = Array.isArray(cameras) ? cameras : [];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4">Cameras</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpen()}
        >
          Add Camera
        </Button>
      </Box>

      <Box sx={{ mb: 4 }}>
        <Typography variant="h5" sx={{ mb: 2 }}>Local Cameras</Typography>
        <CameraScanner />
      </Box>

      <Divider sx={{ my: 4 }} />

      <Box sx={{ mb: 4 }}>
        <Typography variant="h5" sx={{ mb: 2 }}>IP Cameras</Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 3 }}>
          {cameraList.map((camera: Camera) => (
            <Box key={camera.id}>
              <Card>
                <CardContent>
                  <Typography variant="h6">{camera.name}</Typography>
                  <Typography color="textSecondary" gutterBottom>
                    {camera.rtsp_url}
                  </Typography>
                  <Typography
                    color={camera.is_active ? 'success.main' : 'error.main'}
                  >
                    {camera.is_active ? 'Active' : 'Inactive'}
                  </Typography>
                  <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
                    <IconButton
                      color="primary"
                      onClick={() => handleOpen(camera)}
                    >
                      <EditIcon />
                    </IconButton>
                    <IconButton
                      color="error"
                      onClick={() => deleteMutation.mutate(camera.id)}
                    >
                      <DeleteIcon />
                    </IconButton>
                  </Box>
                </CardContent>
              </Card>
            </Box>
          ))}
        </Box>
      </Box>

      <Dialog open={open} onClose={handleClose}>
        <DialogTitle>
          {selectedCamera ? 'Edit Camera' : 'Add Camera'}
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
            <TextField
              margin="dense"
              label="RTSP URL"
              fullWidth
              value={formData.rtsp_url}
              onChange={(e) =>
                setFormData({ ...formData, rtsp_url: e.target.value })
              }
            />
            <TextField
              margin="dense"
              label="Device ID"
              type="number"
              fullWidth
              value={formData.device_id}
              onChange={(e) =>
                setFormData({ ...formData, device_id: Number(e.target.value) })
              }
            />
            <TextField
              margin="dense"
              label="FPS"
              type="number"
              fullWidth
              value={formData.fps}
              onChange={(e) =>
                setFormData({ ...formData, fps: Number(e.target.value) })
              }
            />
            <FormControl fullWidth margin="dense">
              <InputLabel>Resolution</InputLabel>
              <Select
                value={formData.resolution?.join('x')}
                label="Resolution"
                onChange={(e) => {
                  const [width, height] = e.target.value.split('x').map(Number);
                  setFormData({ ...formData, resolution: [width, height] });
                }}
              >
                <MenuItem value="640x480">640x480</MenuItem>
                <MenuItem value="1280x720">1280x720</MenuItem>
                <MenuItem value="1920x1080">1920x1080</MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth margin="dense">
              <InputLabel>Status</InputLabel>
              <Select
                value={formData.is_active}
                label="Status"
                onChange={(e) =>
                  setFormData({ ...formData, is_active: e.target.value === 'true' })
                }
              >
                <MenuItem value="true">Active</MenuItem>
                <MenuItem value="false">Inactive</MenuItem>
              </Select>
            </FormControl>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleClose}>Cancel</Button>
            <Button type="submit" variant="contained" color="primary">
              {selectedCamera ? 'Update' : 'Create'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Box>
  );
};

export default Cameras;