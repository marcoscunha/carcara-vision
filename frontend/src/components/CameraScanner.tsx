import React, { useState } from 'react'
import { Button, List, ListItem, ListItemText, Typography, Box, CircularProgress } from '@mui/material'
import { cameraApi, CameraInfo } from '../services/api'
import { useCreateCamera, useCameras } from '../hooks/useQueries'
import { Camera } from '../types'

export const CameraScanner: React.FC = () => {
  const [cameras, setCameras] = useState<CameraInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: registeredCameras } = useCameras()
  const createCameraMutation = useCreateCamera()

  const handleScan = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await cameraApi.scan()
      // Filter out cameras that are already registered (match by persistent device_path)
      const registeredDevicePaths = new Set(
        (Array.isArray(registeredCameras) ? registeredCameras : []).map((c: Camera) => c.device_path).filter(Boolean),
      )
      const registeredDeviceIds = new Set(
        (Array.isArray(registeredCameras) ? registeredCameras : []).map((c: Camera) => c.device_id),
      )
      const availableCameras = response.data.filter(
        (camera) => !registeredDevicePaths.has(camera.device_path) && !registeredDeviceIds.has(camera.device_id),
      )
      setCameras(availableCameras)
    } catch (err) {
      setError('Failed to scan for cameras')
      console.error('Error scanning cameras:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleAddCamera = async (camera: CameraInfo) => {
    createCameraMutation.mutate(
      {
        name: camera.name,
        device_id: camera.device_id,
        device_path: camera.device_path,
        camera_type: 'local',
        is_active: true,
      },
      {
        onSuccess: () => {
          // Remove the added camera from the scanned list
          setCameras((prev) => prev.filter((c) => c.device_path !== camera.device_path))
        },
        onError: (err) => {
          console.error('Error adding camera:', err)
        },
      },
    )
  }

  return (
    <Box>
      <Button variant="contained" onClick={handleScan} disabled={loading} className="camera-scanner__button">
        {loading ? <CircularProgress size={24} /> : 'Scan for Cameras'}
      </Button>

      {error && (
        <Typography color="error" className="camera-scanner__error">
          {error}
        </Typography>
      )}

      {cameras.length > 0 && (
        <List>
          {cameras.map((camera) => (
            <ListItem
              key={camera.device_path || camera.device_id}
              secondaryAction={
                <Button
                  variant="outlined"
                  onClick={() => handleAddCamera(camera)}
                  disabled={createCameraMutation.isPending}
                >
                  {createCameraMutation.isPending ? <CircularProgress size={20} /> : 'Add Camera'}
                </Button>
              }
            >
              <ListItemText
                primary={camera.name || `Camera ${camera.device_id}`}
                secondary={
                  <>
                    <Typography component="span" variant="body2" color="text.primary">
                      Device Path: {camera.device_path}
                    </Typography>
                    <br />
                    <Typography component="span" variant="body2" color="text.primary">
                      Resolution: {camera.resolution[0]}x{camera.resolution[1]}
                    </Typography>
                    <br />
                    <Typography component="span" variant="body2" color="text.primary">
                      FPS: {camera.fps}
                    </Typography>
                    <br />
                    <Typography component="span" variant="body2" color="text.primary">
                      Physical Address: {camera.physical_address || 'N/A'}
                    </Typography>
                    <br />
                    <Typography component="span" variant="body2" color="text.primary">
                      USB ID: {camera.usb_id || 'N/A'}
                    </Typography>
                    <br />
                    <Typography component="span" variant="body2" color="text.primary">
                      Supported Resolutions:{' '}
                      {camera.supported_resolutions.map(([width, height]) => `${width}x${height}`).join(', ')}
                    </Typography>
                    <br />
                    <Typography
                      component="span"
                      variant="body2"
                      color={camera.is_available ? 'success.main' : 'error.main'}
                    >
                      Status: {camera.is_available ? 'Available' : 'Not Available'}
                    </Typography>
                  </>
                }
              />
            </ListItem>
          ))}
        </List>
      )}
    </Box>
  )
}
