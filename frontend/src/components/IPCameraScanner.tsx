import React, { useState } from 'react'
import {
  Button,
  List,
  ListItem,
  ListItemText,
  Typography,
  Box,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Chip,
  Stack,
} from '@mui/material'
import { Wifi as WifiIcon, Search as SearchIcon } from '@mui/icons-material'
import { useCreateCamera, useCameras, useDiscoverCameras } from '../hooks/useQueries'
import { DiscoveredCamera, DiscoveryProtocol, Camera } from '../types'

export const IPCameraScanner: React.FC = () => {
  const [cameras, setCameras] = useState<DiscoveredCamera[]>([])
  const [protocol, setProtocol] = useState<DiscoveryProtocol>('mdns')
  const [timeout, setTimeout] = useState<number>(3)
  const [rtspUrlOverrides, setRtspUrlOverrides] = useState<Record<string, string>>({})

  const { data: registeredCameras } = useCameras()
  const discoverMutation = useDiscoverCameras()
  const createCameraMutation = useCreateCamera()

  const handleScan = async () => {
    discoverMutation.mutate(
      { protocol, timeout },
      {
        onSuccess: (data) => {
          // Filter out cameras that are already registered by IP
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
          setCameras(availableCameras)
        },
      },
    )
  }

  const handleAddCamera = async (camera: DiscoveredCamera) => {
    const rtspUrl = rtspUrlOverrides[camera.ip] || camera.rtsp_url
    if (!rtspUrl) {
      return
    }

    createCameraMutation.mutate(
      {
        name: camera.name || `IP Camera (${camera.ip})`,
        rtsp_url: rtspUrl,
        camera_type: 'rtsp',
        is_active: true,
      },
      {
        onSuccess: () => {
          setCameras((prev) => prev.filter((c) => c.ip !== camera.ip))
          // Clear the override
          setRtspUrlOverrides((prev) => {
            // eslint-disable-next-line @typescript-eslint/no-unused-vars
            const { [camera.ip]: _removed, ...rest } = prev
            return rest
          })
        },
        onError: (err) => {
          console.error('Error adding camera:', err)
        },
      },
    )
  }

  const handleRtspUrlChange = (ip: string, value: string) => {
    setRtspUrlOverrides((prev) => ({ ...prev, [ip]: value }))
  }

  const getRtspUrl = (camera: DiscoveredCamera): string => {
    return rtspUrlOverrides[camera.ip] || camera.rtsp_url || `rtsp://${camera.ip}:554/stream1`
  }

  return (
    <Box>
      <Stack direction="row" spacing={2} alignItems="center" className="camera-scanner__controls">
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel id="protocol-label">Protocol</InputLabel>
          <Select
            labelId="protocol-label"
            value={protocol}
            label="Protocol"
            onChange={(e) => setProtocol(e.target.value as DiscoveryProtocol)}
          >
            <MenuItem value="mdns">mDNS</MenuItem>
            <MenuItem value="onvif">ONVIF</MenuItem>
            <MenuItem value="both">Both</MenuItem>
          </Select>
        </FormControl>
        <TextField
          size="small"
          label="Timeout (s)"
          type="number"
          value={timeout}
          onChange={(e) => setTimeout(Math.max(0.5, Math.min(10, parseFloat(e.target.value) || 3)))}
          sx={{ width: 100 }}
          InputProps={{ inputProps: { min: 0.5, max: 10, step: 0.5 } }}
        />
        <Button
          variant="contained"
          onClick={handleScan}
          disabled={discoverMutation.isPending}
          startIcon={discoverMutation.isPending ? <CircularProgress size={20} /> : <SearchIcon />}
          className="camera-scanner__button"
        >
          Scan Network
        </Button>
      </Stack>

      {discoverMutation.isError && (
        <Typography color="error" className="camera-scanner__error">
          Failed to scan for IP cameras
        </Typography>
      )}

      {cameras.length === 0 && !discoverMutation.isPending && discoverMutation.isSuccess && (
        <Typography color="text.secondary" sx={{ mt: 2 }}>
          No IP cameras found on the network.
        </Typography>
      )}

      {cameras.length > 0 && (
        <List>
          {cameras.map((camera) => (
            <ListItem key={camera.ip} sx={{ flexDirection: 'column', alignItems: 'stretch', gap: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <WifiIcon fontSize="small" color="primary" />
                      <Typography variant="subtitle1">{camera.name || `IP Camera (${camera.ip})`}</Typography>
                      <Chip
                        label={camera.protocol.toUpperCase()}
                        size="small"
                        variant="outlined"
                        color={camera.protocol === 'onvif' ? 'primary' : 'secondary'}
                      />
                    </Box>
                  }
                  secondary={`IP: ${camera.ip}`}
                />
                <Button
                  variant="outlined"
                  onClick={() => handleAddCamera(camera)}
                  disabled={createCameraMutation.isPending || !getRtspUrl(camera)}
                >
                  {createCameraMutation.isPending ? <CircularProgress size={20} /> : 'Add Camera'}
                </Button>
              </Box>
              <TextField
                size="small"
                fullWidth
                label="RTSP URL"
                value={getRtspUrl(camera)}
                onChange={(e) => handleRtspUrlChange(camera.ip, e.target.value)}
                placeholder={`rtsp://${camera.ip}:554/stream1`}
                helperText={
                  camera.protocol === 'onvif'
                    ? 'ONVIF device detected. Enter the RTSP stream URL.'
                    : 'Verify or modify the RTSP URL before adding.'
                }
              />
            </ListItem>
          ))}
        </List>
      )}
    </Box>
  )
}
