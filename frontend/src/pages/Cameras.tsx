import React, { useState } from 'react'
import {
  Box,
  Button,
  IconButton,
  Typography,
  Chip,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material'
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Videocam as VideocamIcon,
  Circle as CircleIcon,
} from '@mui/icons-material'
import { useCameras, useCreateCamera, useUpdateCamera, useDeleteCamera } from '../hooks/useQueries'
import { Camera } from '../types'
import { ConfirmDeleteDialog, CameraFormDialog, CameraFormData } from '../components/dialogs'

const Cameras: React.FC = () => {
  const [formDialogOpen, setFormDialogOpen] = useState(false)
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [cameraToDelete, setCameraToDelete] = useState<Camera | null>(null)

  // TanStack Query hooks for server state management
  const { data: cameras, isLoading } = useCameras()

  const createMutation = useCreateCamera()
  const updateMutation = useUpdateCamera()
  const deleteMutation = useDeleteCamera()

  const handleOpenFormDialog = (camera?: Camera) => {
    setSelectedCamera(camera || null)
    setFormDialogOpen(true)
  }

  const handleCloseFormDialog = () => {
    setFormDialogOpen(false)
    setSelectedCamera(null)
  }

  const handleOpenDeleteDialog = (camera: Camera) => {
    setCameraToDelete(camera)
    setDeleteDialogOpen(true)
  }

  const handleCloseDeleteDialog = () => {
    setDeleteDialogOpen(false)
    setCameraToDelete(null)
  }

  const handleConfirmDelete = () => {
    if (cameraToDelete) {
      deleteMutation.mutate(cameraToDelete.id, {
        onSuccess: () => handleCloseDeleteDialog(),
      })
    }
  }

  const handleFormSubmit = (formData: CameraFormData) => {
    if (selectedCamera) {
      updateMutation.mutate({ id: selectedCamera.id, data: formData }, { onSuccess: () => handleCloseFormDialog() })
    } else {
      createMutation.mutate(formData, { onSuccess: () => handleCloseFormDialog() })
    }
  }

  if (isLoading) {
    return (
      <Box>
        <Box className="loading-header">
          <Skeleton variant="text" width={150} height={40} />
          <Skeleton variant="rounded" width={140} height={40} />
        </Box>
        <Skeleton variant="rounded" height={200} />
      </Box>
    )
  }

  const cameraList = Array.isArray(cameras) ? cameras : []

  return (
    <Box className="fade-in">
      {/* Page Header */}
      <Box className="page-header">
        <Box>
          <Typography variant="h4" className="page-header__title">
            Cameras
          </Typography>
          <Typography variant="body2" color="text.secondary" className="page-header__subtitle">
            Manage your video surveillance cameras
          </Typography>
        </Box>
        <Box className="page-header__actions">
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpenFormDialog()}
            className="page-header__action"
          >
            Add Camera
          </Button>
        </Box>
      </Box>

      {/* Registered Cameras Section */}
      <Box className="section">
        <Box className="section-header">
          <Box className="section-header__accent" />
          <Typography variant="h5" className="section-header__title">
            Registered Cameras
          </Typography>
          <Chip label={cameraList.length} size="small" className="section-header__count" />
        </Box>

        {cameraList.length === 0 ? (
          <Box className="empty-panel">
            <VideocamIcon className="empty-panel__icon" />
            <Typography color="text.secondary" variant="h6" className="empty-panel__title">
              No cameras configured
            </Typography>
            <Typography color="text.secondary" variant="body2">
              Click "Add Camera" or scan for local cameras to add your first camera
            </Typography>
          </Box>
        ) : (
          <TableContainer component={Paper} className="table-card">
            <Table>
              <TableHead>
                <TableRow className="table-head-row">
                  <TableCell className="table-head-cell">Name</TableCell>
                  <TableCell className="table-head-cell">Type</TableCell>
                  <TableCell className="table-head-cell">URL / Device</TableCell>
                  <TableCell className="table-head-cell">Status</TableCell>
                  <TableCell className="table-head-cell" align="right">
                    Actions
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {cameraList.map((camera: Camera) => (
                  <TableRow key={camera.id} className="table-row-hover">
                    <TableCell>
                      <Box className="table-name">
                        <VideocamIcon className="table-name__icon" />
                        <Typography variant="body2" className="table-name__text">
                          {camera.name}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={camera.camera_type || 'IP'}
                        size="small"
                        variant="outlined"
                        className="chip-capitalize"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary" className="table-url">
                        {camera.rtsp_url || `Device ${camera.device_id}`}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        icon={<CircleIcon className="chip-icon--tiny" />}
                        label={camera.is_active ? 'Active' : 'Inactive'}
                        size="small"
                        color={camera.is_active ? 'success' : 'error'}
                        className={`status-chip ${camera.is_active ? 'status-chip--active' : ''}`}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={() => handleOpenFormDialog(camera)}
                        className="icon-button--primary"
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => handleOpenDeleteDialog(camera)}
                        className="icon-button--error"
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
  )
}

export default Cameras
