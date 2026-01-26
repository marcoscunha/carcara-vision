import React, { useState, useEffect } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { Camera } from '../../types';

export interface CameraFormData {
  name: string;
  rtsp_url: string;
  is_active: boolean;
  device_id: number;
  resolution: [number, number];
  fps: number;
  is_available: boolean;
}

const initialFormData: CameraFormData = {
  name: '',
  rtsp_url: '',
  is_active: true,
  device_id: 0,
  resolution: [0, 0],
  fps: 0,
  is_available: false,
};

export interface CameraFormDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: CameraFormData) => void;
  camera?: Camera | null;
  isLoading?: boolean;
}

export const CameraFormDialog: React.FC<CameraFormDialogProps> = ({
  open,
  onClose,
  onSubmit,
  camera,
  isLoading = false,
}) => {
  const [formData, setFormData] = useState<CameraFormData>(initialFormData);

  const isEditMode = Boolean(camera);

  // Reset or populate form when dialog opens or camera changes
  useEffect(() => {
    if (open) {
      if (camera) {
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
        setFormData(initialFormData);
      }
    }
  }, [open, camera]);

  const handleClose = () => {
    setFormData(initialFormData);
    onClose();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <Dialog open={open} onClose={handleClose}>
      <DialogTitle>
        {isEditMode ? 'Edit Camera' : 'Add Camera'}
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
            disabled={isLoading}
          />
          <TextField
            margin="dense"
            label="RTSP URL"
            fullWidth
            value={formData.rtsp_url}
            onChange={(e) =>
              setFormData({ ...formData, rtsp_url: e.target.value })
            }
            disabled={isLoading}
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
            disabled={isLoading}
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
            disabled={isLoading}
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
              disabled={isLoading}
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
              disabled={isLoading}
            >
              <MenuItem value="true">Active</MenuItem>
              <MenuItem value="false">Inactive</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={isLoading}
          >
            {isLoading
              ? isEditMode
                ? 'Updating...'
                : 'Creating...'
              : isEditMode
              ? 'Update'
              : 'Create'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default CameraFormDialog;
