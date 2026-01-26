import React, { useState } from 'react';
import {
  Box,
  Button,
  IconButton,
  Typography,
  Divider,
  Chip,
  alpha,
  useTheme,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
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
import { ConfirmDeleteDialog, CameraFormDialog, CameraFormData } from '../components/dialogs';

const Cameras: React.FC = () => {
  const [formDialogOpen, setFormDialogOpen] = useState(false);
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [cameraToDelete, setCameraToDelete] = useState<Camera | null>(null);
  const theme = useTheme();

  // TanStack Query hooks for server state management
  const { data: cameras, isLoading } = useCameras();

  const createMutation = useCreateCamera();
  const updateMutation = useUpdateCamera();
  const deleteMutation = useDeleteCamera();

  const handleOpenFormDialog = (camera?: Camera) => {
    setSelectedCamera(camera || null);
    setFormDialogOpen(true);
  };

  const handleCloseFormDialog = () => {
    setFormDialogOpen(false);
    setSelectedCamera(null);
  };

  const handleOpenDeleteDialog = (camera: Camera) => {
    setCameraToDelete(camera);
    setDeleteDialogOpen(true);
  };

  const handleCloseDeleteDialog = () => {
    setDeleteDialogOpen(false);
    setCameraToDelete(null);
  };

  const handleConfirmDelete = () => {
    if (cameraToDelete) {
      deleteMutation.mutate(cameraToDelete.id, {
        onSuccess: () => handleCloseDeleteDialog(),
      });
    }
  };

  const handleFormSubmit = (formData: CameraFormData) => {
    if (selectedCamera) {
      updateMutation.mutate(
        { id: selectedCamera.id, data: formData },
        { onSuccess: () => handleCloseFormDialog() }
      );
    } else {
      createMutation.mutate(formData, { onSuccess: () => handleCloseFormDialog() });
    }
  };

  if (isLoading) {
    return (
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
          <Skeleton variant="text" width={150} height={40} />
          <Skeleton variant="rounded" width={140} height={40} />
        </Box>
        <Skeleton variant="rounded" height={200} />
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
          onClick={() => handleOpenFormDialog()}
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
          <Typography variant="h5" sx={{ fontWeight: 600 }}>Registered Cameras</Typography>
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
              No cameras configured
            </Typography>
            <Typography color="text.secondary" variant="body2">
              Click "Add Camera" or scan for local cameras to add your first camera
            </Typography>
          </Box>
        ) : (
          <TableContainer component={Paper} sx={{ borderRadius: 2 }}>
            <Table>
              <TableHead>
                <TableRow sx={{ backgroundColor: alpha(theme.palette.primary.main, 0.08) }}>
                  <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>URL / Device</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Resolution</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>FPS</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {cameraList.map((camera: Camera) => (
                  <TableRow
                    key={camera.id}
                    sx={{
                      '&:hover': { backgroundColor: alpha(theme.palette.action.hover, 0.5) },
                    }}
                  >
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <VideocamIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {camera.name}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={camera.camera_type || 'IP'}
                        size="small"
                        variant="outlined"
                        sx={{ textTransform: 'capitalize' }}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{
                          maxWidth: 200,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {camera.rtsp_url || `Device ${camera.device_id}`}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {camera.resolution ? `${camera.resolution[0]}x${camera.resolution[1]}` : '-'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{camera.fps || '-'}</Typography>
                    </TableCell>
                    <TableCell>
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
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={() => handleOpenFormDialog(camera)}
                        sx={{
                          color: 'primary.main',
                          '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.12) },
                        }}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => handleOpenDeleteDialog(camera)}
                        sx={{
                          color: 'error.main',
                          '&:hover': { backgroundColor: alpha(theme.palette.error.main, 0.12) },
                        }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      {/* Camera Form Dialog */}
      <CameraFormDialog
        open={formDialogOpen}
        onClose={handleCloseFormDialog}
        onSubmit={handleFormSubmit}
        camera={selectedCamera}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDeleteDialog
        open={deleteDialogOpen}
        onClose={handleCloseDeleteDialog}
        onConfirm={handleConfirmDelete}
        title="Delete Camera"
        itemName={cameraToDelete?.name || ''}
        warningMessage="Warning: All streams associated with this camera will also be permanently deleted."
        isLoading={deleteMutation.isPending}
      />
    </Box>
  );
};

export default Cameras;