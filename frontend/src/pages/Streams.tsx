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
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useStreams, useCreateStream, useUpdateStream, useDeleteStream, useCameras } from '../hooks/useQueries';
import { Stream, Camera } from '../types';
import CameraStream from '../components/CameraStream';

const Streams: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [selectedStream, setSelectedStream] = useState<Stream | null>(null);
  const [formData, setFormData] = useState({
    camera_id: 0,
    status: 'stopped',
    current_frame: 0,
    stream_metadata: {},
  });

  // TanStack Query hooks for server state management
  const {
    data: streams,
    isLoading: streamsLoading,
    isError: streamsError,
    error: streamsErrorData,
    refetch: refetchStreams
  } = useStreams();

  const {
    data: cameras,
    isLoading: camerasLoading,
    isError: camerasError
  } = useCameras();

  const createMutation = useCreateStream();
  const updateMutation = useUpdateStream();
  const deleteMutation = useDeleteStream();

  const handleOpen = (stream?: Stream) => {
    if (stream) {
      setSelectedStream(stream);
      setFormData({
        camera_id: stream.camera_id,
        status: stream.status,
        current_frame: stream.current_frame,
        stream_metadata: stream.stream_metadata,
      });
    } else {
      setSelectedStream(null);
      setFormData({
        camera_id: 0,
        status: 'stopped',
        current_frame: 0,
        stream_metadata: {},
      });
    }
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
    setSelectedStream(null);
    setFormData({
      camera_id: 0,
      status: 'stopped',
      current_frame: 0,
      stream_metadata: {},
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedStream) {
      updateMutation.mutate(
        { id: selectedStream.id, data: formData },
        { onSuccess: () => handleClose() }
      );
    } else {
      createMutation.mutate(formData, { onSuccess: () => handleClose() });
    }
  };

  if (streamsLoading || camerasLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (streamsError || camerasError) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        Error loading data: {streamsErrorData?.message || 'Unknown error'}
      </Alert>
    );
  }

  const streamList = Array.isArray(streams) ? streams : [];
  const cameraList = Array.isArray(cameras) ? cameras : [];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4">Streams</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => refetchStreams()}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpen()}
          >
            Add Stream
          </Button>
        </Box>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 3 }}>
        {streamList.map((stream: Stream) => {
          const camera = cameraList.find((c: Camera) => c.id === stream.camera_id);
          return (
            <Box key={stream.id}>
              <Card>
                <CardContent>
                  <Typography variant="h6">{camera?.name || 'Unknown Camera'}</Typography>
                  <Typography color="textSecondary" gutterBottom>
                    Status: {stream.status}
                  </Typography>
                  <Typography color="textSecondary" gutterBottom>
                    Frame: {stream.current_frame}
                  </Typography>
                  <CameraStream stream={stream} />
                  <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
                    <IconButton
                      color="primary"
                      onClick={() => handleOpen(stream)}
                    >
                      <EditIcon />
                    </IconButton>
                    <IconButton
                      color="error"
                      onClick={() => deleteMutation.mutate(stream.id)}
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
          {selectedStream ? 'Edit Stream' : 'Add Stream'}
        </DialogTitle>
        <form onSubmit={handleSubmit}>
          <DialogContent>
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
  );
};

export default Streams;