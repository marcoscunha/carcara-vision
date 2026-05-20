import React, { useState, useEffect } from 'react'
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
  Tabs,
  Tab,
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
  Stack,
  Chip,
} from '@mui/material'
import { Search as SearchIcon, Wifi as WifiIcon } from '@mui/icons-material'
import { Camera, DiscoveredCamera, DiscoveryProtocol } from '../../types'
import { CameraInfo } from '../../services/api'
import { useCreateCamera, useCameras, useDiscoverCameras } from '../../hooks/useQueries'
import { cameraApi } from '../../services/api'

export interface CameraFormData {
  name: string
  rtsp_url: string | null
  is_active: boolean
  device_id: number
  device_path?: string | null
  camera_type?: string
  resolution: [number, number]
  fps: number
  is_available: boolean
}

const initialFormData: CameraFormData = {
  name: '',
  rtsp_url: '',
  is_active: true,
  device_id: 0,
  device_path: null,
  camera_type: 'ip',
  resolution: [0, 0],
  fps: 0,
  is_available: false,
}

export interface CameraFormDialogProps {
  open: boolean
  onClose: () => void
  onSubmit: (data: CameraFormData) => void
  camera?: Camera | null
  isLoading?: boolean
}

interface TabPanelProps {
  children?: React.ReactNode
  index: number
  value: number
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props
  return (
    <div hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  )
}

export const CameraFormDialog: React.FC<CameraFormDialogProps> = ({
  open,
  onClose,
  onSubmit,
  camera,
  isLoading = false,
}) => {
  const [formData, setFormData] = useState<CameraFormData>(initialFormData)
  const [tabValue, setTabValue] = useState(2)
  const [localCameras, setLocalCameras] = useState<CameraInfo[]>([])
  const [ipCameras, setIpCameras] = useState<DiscoveredCamera[]>([])
  const [protocol] = useState<DiscoveryProtocol>('both')
  const [timeout] = useState<number>(5)
  const [rtspUrlOverrides, setRtspUrlOverrides] = useState<Record<string, string>>({})
  const [scanningLocal, setScanningLocal] = useState(false)
  const [scanningIP, setScanningIP] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)

  const isEditMode = Boolean(camera)
  const { data: registeredCameras } = useCameras()
  const discoverMutation = useDiscoverCameras()
  const createCameraMutation = useCreateCamera()

  // Reset or populate form when dialog opens or camera changes
  useEffect(() => {
    if (open) {
      if (camera) {
        setFormData({
          name: camera.name,
          rtsp_url: camera.rtsp_url,
          is_active: camera.is_active,
          device_id: camera.device_id,
          device_path: camera.device_path,
          camera_type: camera.camera_type,
          resolution: camera.resolution,
          fps: camera.fps,
          is_available: camera.is_available,
        })
        setTabValue(0)
      } else {
        setFormData(initialFormData)
        setTabValue(2)
      }
    }
  }, [open, camera])

  const handleClose = () => {
    setFormData(initialFormData)
    setLocalCameras([])
    setIpCameras([])
    setScanError(null)
    onClose()
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  const handleScanLocal = async () => {
    setScanningLocal(true)
    setScanError(null)
    try {
      const response = await cameraApi.scan()
      const registeredDevicePaths = new Set(
        (Array.isArray(registeredCameras) ? registeredCameras : []).map((c: Camera) => c.device_path).filter(Boolean),
      )
      const registeredDeviceIds = new Set(
        (Array.isArray(registeredCameras) ? registeredCameras : []).map((c: Camera) => c.device_id),
      )
      const availableCameras = response.data.filter(
        (camera) => !registeredDevicePaths.has(camera.device_path) && !registeredDeviceIds.has(camera.device_id),
      )
      setLocalCameras(availableCameras)
    } catch (err) {
      setScanError('Failed to scan for local cameras')
      console.error('Error scanning cameras:', err)
    } finally {
      setScanningLocal(false)
    }
  }

  const handleScanNetwork = async () => {
    setScanningIP(true)
    setScanError(null)
    discoverMutation.mutate(
      { protocol, timeout },
      {
        onSuccess: (data) => {
          const registeredIPs = new Set(
            (Array.isArray(registeredCameras) ? registeredCameras : [])
              .map((c: Camera) => {
                if (c.rtsp_url) {
                  try {
                    const url = new URL(c.rtsp_url)
                    return url.hostname
                  } catch {
                    return null
                  }
                }
                return null
              })
              .filter(Boolean),
          )
          const availableCameras = data.filter((camera) => !registeredIPs.has(camera.ip))
          setIpCameras(availableCameras)
          setScanningIP(false)
        },
        onError: () => {
          setScanError('Failed to scan for IP cameras')
          setScanningIP(false)
        },
      },
    )
  }

  const handleAddLocalCamera = (camera: CameraInfo) => {
    const data: CameraFormData = {
      name: camera.name || `Camera ${camera.device_id}`,
      rtsp_url: null,
      is_active: true,
      device_id: camera.device_id,
      device_path: camera.device_path,
      camera_type: 'local',
      resolution: camera.resolution,
      fps: camera.fps,
      is_available: camera.is_available,
    }
    setScanError(null)
    createCameraMutation.mutate(data, {
      onSuccess: () => {
        setLocalCameras((prev) => prev.filter((c) => c.device_path !== camera.device_path))
      },
      onError: () => {
        setScanError('Failed to add camera')
      },
    })
  }

  const handleAddIPCamera = (camera: DiscoveredCamera) => {
    const rtspUrl = rtspUrlOverrides[camera.ip] || camera.rtsp_url || `rtsp://${camera.ip}:554/stream1`
    const data: CameraFormData = {
      name: camera.name || `IP Camera (${camera.ip})`,
      rtsp_url: rtspUrl,
      is_active: true,
      device_id: 0,
      device_path: null,
      camera_type: 'ip',
      resolution: [0, 0],
      fps: 0,
      is_available: true,
    }
    setScanError(null)
    createCameraMutation.mutate(data, {
      onSuccess: () => {
        setIpCameras((prev) => prev.filter((c) => c.ip !== camera.ip))
        setRtspUrlOverrides((prev) => {
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
          const { [camera.ip]: _, ...rest } = prev
          return rest
        })
      },
      onError: () => {
        setScanError('Failed to add camera')
      },
    })
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isEditMode ? 'Edit Camera' : 'Add Camera'}</DialogTitle>
      <Tabs
        value={tabValue}
        onChange={(_e, value) => setTabValue(value)}
        sx={{ borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab label="Manual Entry" />
        <Tab label="Local Camera" />
        <Tab label="Network Camera" />
      </Tabs>

      <form onSubmit={handleSubmit}>
        <DialogContent>
          {/* Manual Entry Tab */}
          <TabPanel value={tabValue} index={0}>
            <Stack spacing={2}>
              <TextField
                autoFocus
                margin="dense"
                label="Camera Name"
                fullWidth
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                disabled={isLoading}
              />
              <TextField
                margin="dense"
                label="RTSP URL"
                fullWidth
                value={formData.rtsp_url}
                onChange={(e) => setFormData({ ...formData, rtsp_url: e.target.value })}
                disabled={isLoading}
                placeholder="rtsp://192.168.1.100:554/stream"
              />
              <FormControl fullWidth margin="dense">
                <InputLabel>Resolution</InputLabel>
                <Select
                  value={formData.resolution?.join('x') || ''}
                  label="Resolution"
                  onChange={(e) => {
                    const [width, height] = e.target.value.split('x').map(Number)
                    setFormData({ ...formData, resolution: [width, height] })
                  }}
                  disabled={isLoading}
                >
                  <MenuItem value="640x480">640x480</MenuItem>
                  <MenuItem value="1280x720">1280x720</MenuItem>
                  <MenuItem value="1920x1080">1920x1080</MenuItem>
                </Select>
              </FormControl>
              <TextField
                margin="dense"
                label="FPS"
                type="number"
                fullWidth
                value={formData.fps}
                onChange={(e) => setFormData({ ...formData, fps: Number(e.target.value) })}
                disabled={isLoading}
              />
              <FormControl fullWidth margin="dense">
                <InputLabel>Status</InputLabel>
                <Select
                  value={formData.is_active ? 'true' : 'false'}
                  label="Status"
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.value === 'true' })}
                  disabled={isLoading}
                >
                  <MenuItem value="true">Active</MenuItem>
                  <MenuItem value="false">Inactive</MenuItem>
                </Select>
              </FormControl>
            </Stack>
          </TabPanel>

          {/* Local Camera Scan Tab */}
          <TabPanel value={tabValue} index={1}>
            <Stack spacing={2}>
              {scanError && (
                <Typography color="error" variant="body2">
                  {scanError}
                </Typography>
              )}

              {localCameras.length === 0 && !scanningLocal && (
                <Typography color="text.secondary" variant="body2">
                  Click the scan button below to search for connected cameras
                </Typography>
              )}

              {localCameras.length > 0 && (
                <List sx={{ maxHeight: 300, overflow: 'auto' }}>
                  {localCameras.map((camera) => (
                    <ListItem
                      key={camera.device_path || camera.device_id}
                      secondaryAction={
                        <Button
                          variant="outlined"
                          size="small"
                          onClick={() => handleAddLocalCamera(camera)}
                          disabled={isLoading || createCameraMutation.isPending}
                        >
                          Add
                        </Button>
                      }
                    >
                      <ListItemText
                        primary={camera.name || `Camera ${camera.device_id}`}
                        secondary={
                          <Box component="span" sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 0.5 }}>
                            <Typography variant="caption" color="text.secondary">
                              {camera.resolution[0]}x{camera.resolution[1]}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {camera.fps} fps
                            </Typography>
                            <Chip
                              size="small"
                              label={camera.is_available ? 'Available' : 'Unavailable'}
                              color={camera.is_available ? 'success' : 'error'}
                              variant="outlined"
                            />
                          </Box>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              )}

              <Button
                variant="contained"
                onClick={handleScanLocal}
                disabled={scanningLocal}
                startIcon={scanningLocal ? <CircularProgress size={20} /> : <SearchIcon />}
                fullWidth
              >
                {scanningLocal ? 'Scanning...' : 'Scan for Local Cameras'}
              </Button>
            </Stack>
          </TabPanel>

          {/* Network Camera Scan Tab */}
          <TabPanel value={tabValue} index={2}>
            <Stack spacing={2}>
              {scanError && (
                <Typography color="error" variant="body2">
                  {scanError}
                </Typography>
              )}

              {ipCameras.length === 0 && !scanningIP && (
                <Typography color="text.secondary" variant="body2">
                  Click the scan button below to search for network cameras
                </Typography>
              )}

              {ipCameras.length > 0 && (
                <List sx={{ maxHeight: 300, overflow: 'auto' }}>
                  {ipCameras.map((camera) => (
                    <ListItem
                      key={camera.ip}
                      secondaryAction={
                        <Button
                          variant="outlined"
                          size="small"
                          onClick={() => handleAddIPCamera(camera)}
                          disabled={isLoading || createCameraMutation.isPending}
                        >
                          Add
                        </Button>
                      }
                    >
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <WifiIcon fontSize="small" color="primary" />
                            <Typography variant="body2">{camera.name || `IP Camera (${camera.ip})`}</Typography>
                            <Chip
                              label={camera.protocol.toUpperCase()}
                              size="small"
                              variant="outlined"
                              sx={{ ml: 'auto' }}
                            />
                          </Box>
                        }
                        secondary={
                          <Typography variant="caption" color="text.secondary">
                            IP: {camera.ip}
                          </Typography>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              )}

              <Button
                variant="contained"
                onClick={handleScanNetwork}
                disabled={scanningIP}
                startIcon={scanningIP ? <CircularProgress size={20} /> : <SearchIcon />}
                fullWidth
              >
                {scanningIP ? 'Scanning...' : 'Scan for Network Cameras'}
              </Button>
            </Stack>
          </TabPanel>
        </DialogContent>

        <DialogActions>
          <Button onClick={handleClose} disabled={isLoading}>
            Cancel
          </Button>
          {tabValue === 0 && (
            <Button type="submit" variant="contained" color="primary" disabled={isLoading}>
              {isLoading ? (isEditMode ? 'Updating...' : 'Creating...') : isEditMode ? 'Update' : 'Create'}
            </Button>
          )}
        </DialogActions>
      </form>
    </Dialog>
  )
}

export default CameraFormDialog
