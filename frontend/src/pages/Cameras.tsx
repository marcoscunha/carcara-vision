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
  Chip,
  alpha,
  useTheme,
  Skeleton,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Videocam as VideocamIcon,
  Circle as CircleIcon,
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
  const theme = useTheme();

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
    return (
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
          <Skeleton variant="text" width={150} height={40} />
          <Skeleton variant="rounded" width={140} height={40} />
        </Box>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 3 }}>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} variant="rounded" height={180} />
          ))}
        </Box>
      </Box>
    );
  }

  const cameraList = Array.isArray(cameras) ? cameras : [];

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
            Cameras
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Manage your video surveillance cameras
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
          Add Camera
        </Button>
      </Box>

      {/* Local Cameras Section */}
      <Box sx={{ mb: 5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
          <Box
            sx={{
              width: 4,
              height: 24,
              borderRadius: 2,
              background: `linear-gradient(180deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
            }}
          />
          <Typography variant="h5" sx={{ fontWeight: 600 }}>Local Cameras</Typography>
        </Box>
        <CameraScanner />
      </Box>

      <Divider sx={{ my: 4 }} />

      {/* IP Cameras Section */}
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
          <Typography variant="h5" sx={{ fontWeight: 600 }}>IP Cameras</Typography>
          <Chip
            label={cameraList.length}
            size="small"
            sx={{
              ml: 1,
              backgroundColor: alpha(theme.palette.primary.main, 0.15),
              color: theme.palette.primary.main,
              fontWeight: 600,
            }}
          />
        </Box>

        {cameraList.length === 0 ? (
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
            <VideocamIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography color="text.secondary" variant="h6" sx={{ mb: 1 }}>
              No IP cameras configured
            </Typography>
            <Typography color="text.secondary" variant="body2">
              Click "Add Camera" to add your first IP camera
            </Typography>
          </Box>
        ) : (
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 3 }}>
            {cameraList.map((camera: Camera) => (
              <Card key={camera.id}>
                <CardContent sx={{ p: 2.5 }}>
                  {/* Camera Preview Placeholder */}
                  <Box
                    sx={{
                      aspectRatio: '16/9',
                      backgroundColor: alpha(theme.palette.background.default, 0.5),
                      borderRadius: 2,
                      mb: 2,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      border: `1px solid ${alpha(theme.palette.divider, 0.3)}`,
                    }}
                  >
                    <VideocamIcon sx={{ fontSize: 40, color: 'text.secondary' }} />
                  </Box>

                  {/* Camera Info */}
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>{camera.name}</Typography>
                    <Chip
                      icon={<CircleIcon sx={{ fontSize: '10px !important' }} />}
                      label={camera.is_active ? 'Active' : 'Inactive'}
                      size="small"
                      color={camera.is_active ? 'success' : 'error'}
                      sx={{
                        '& .MuiChip-icon': {
                          color: 'inherit',
                          animation: camera.is_active ? 'pulse 2s ease-in-out infinite' : 'none',
                        },
                      }}
                    />
                  </Box>

                  <Typography
                    color="text.secondary"
                    variant="body2"
                    sx={{
                      mb: 2,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {camera.rtsp_url || 'No URL configured'}
                  </Typography>

                  {/* Actions */}
                  <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.5 }}>
                    <IconButton
                      size="small"
                      onClick={() => handleOpen(camera)}
                      sx={{
                        color: 'primary.main',
                        '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.12) },
                      }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => deleteMutation.mutate(camera.id)}
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
            ))}
          </Box>
        )}
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