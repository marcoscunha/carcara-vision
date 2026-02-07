import React, { useState } from 'react'
import {
  Box,
  Card,
  CardContent,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Button,
  alpha,
  useTheme,
  Skeleton,
  Divider,
  Chip,
  CircularProgress,
  Alert,
  Tooltip,
  LinearProgress,
} from '@mui/material'
import {
  Save as SaveIcon,
  Settings as SettingsIcon,
  Memory as MemoryIcon,
  Hardware as HardwareIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Computer as ComputerIcon,
  Storage as StorageIcon,
  Speed as SpeedIcon,
} from '@mui/icons-material'
import { useModels, useUpdateModel, useHardwareDetection, useDetectHardware } from '../hooks/useQueries'
import type { Model, AcceleratorStatus, AcceleratorType } from '../types'

// Helper functions for hardware display
const getAcceleratorIcon = (type: AcceleratorType) => {
  if (type.startsWith('nvidia')) return '🟢'
  if (type.startsWith('hailo')) return '🔵'
  if (type.startsWith('google_coral')) return '🟣'
  if (type.startsWith('intel')) return '🔷'
  if (type.startsWith('amd')) return '🔴'
  if (type.startsWith('axelera')) return '🟡'
  if (type === 'cpu') return '⚪'
  return '⚫'
}

const getStatusColor = (status: AcceleratorStatus) => {
  switch (status) {
    case 'available':
      return 'success'
    case 'driver_missing':
      return 'warning'
    case 'unavailable':
    case 'not_detected':
    case 'error':
      return 'error'
    default:
      return 'default'
  }
}

const getStatusIcon = (status: AcceleratorStatus) => {
  switch (status) {
    case 'available':
      return <CheckCircleIcon fontSize="small" />
    case 'driver_missing':
      return <WarningIcon fontSize="small" />
    default:
      return <ErrorIcon fontSize="small" />
  }
}

const formatAcceleratorName = (type: AcceleratorType): string => {
  const names: Record<string, string> = {
    nvidia_gpu: 'NVIDIA GPU',
    nvidia_tensorrt: 'NVIDIA TensorRT',
    nvidia_jetson: 'NVIDIA Jetson',
    google_coral_usb: 'Google Coral USB',
    google_coral_pcie: 'Google Coral PCIe',
    google_coral_m2: 'Google Coral M.2',
    hailo_8: 'Hailo-8',
    hailo_8l: 'Hailo-8L',
    hailo_10: 'Hailo-10',
    intel_openvino: 'Intel OpenVINO',
    intel_movidius: 'Intel Movidius',
    axelera_m2: 'Axelera M.2',
    amd_rocm: 'AMD ROCm',
    cpu: 'CPU',
  }
  return names[type] || type
}

const formatPlatformVendor = (vendor: string): string => {
  const names: Record<string, string> = {
    intel: 'Intel',
    amd: 'AMD',
    nvidia_jetson: 'NVIDIA Jetson',
    raspberry_pi: 'Raspberry Pi',
    orange_pi: 'Orange Pi',
    aetina: 'Aetina',
    rock_pi: 'Rock Pi',
    khadas: 'Khadas',
    generic_arm: 'Generic ARM',
    generic_x86: 'Generic x86',
    unknown: 'Unknown',
  }
  return names[vendor] || vendor
}

const formatArchitecture = (arch: string): string => {
  const names: Record<string, string> = {
    x86_64: 'x86-64 (64-bit)',
    x86: 'x86 (32-bit)',
    arm64: 'ARM64 (AArch64)',
    armv7: 'ARMv7 (32-bit)',
    armv8: 'ARMv8',
    unknown: 'Unknown',
  }
  return names[arch] || arch
}

const Settings: React.FC = () => {
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.5)
  const theme = useTheme()

  // TanStack Query hooks for server state management
  const { data: models, isLoading } = useModels()
  const updateMutation = useUpdateModel()

  // Hardware detection hooks
  const { data: hardwareData, isLoading: isHardwareLoading } = useHardwareDetection(true)
  const detectHardwareMutation = useDetectHardware()

  const handleSave = () => {
    if (selectedModel) {
      updateMutation.mutate({
        name: selectedModel,
        data: { confidence_threshold: confidenceThreshold },
      })
    }
  }

  const handleDetectHardware = () => {
    detectHardwareMutation.mutate(true)
  }

  if (isLoading) {
    return (
      <Box>
        <Skeleton variant="text" width={120} height={40} sx={{ mb: 3 }} />
        <Skeleton variant="rounded" height={300} />
      </Box>
    )
  }

  const modelList = models?.data || []

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
            Settings
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Configure system and detection parameters
          </Typography>
        </Box>
      </Box>

      {/* Settings Cards */}
      <Box sx={{ display: 'grid', gap: 3 }}>
        {/* Object Detection Settings */}
        <Card>
          <CardContent sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
              <Box
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: 2,
                  background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.2)} 0%, ${alpha(theme.palette.primary.dark, 0.2)} 100%)`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <MemoryIcon sx={{ color: 'primary.main' }} />
              </Box>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  Object Detection
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Configure AI model and detection sensitivity
                </Typography>
              </Box>
            </Box>

            <Divider sx={{ mb: 3 }} />

            <FormControl fullWidth sx={{ mb: 4 }}>
              <InputLabel>Detection Model</InputLabel>
              <Select value={selectedModel} label="Detection Model" onChange={(e) => setSelectedModel(e.target.value)}>
                {modelList.map((model: Model) => (
                  <MenuItem key={model.name} value={model.name}>
                    {model.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box sx={{ mb: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography sx={{ fontWeight: 500 }}>Confidence Threshold</Typography>
                <Typography
                  sx={{
                    fontWeight: 600,
                    color: 'primary.main',
                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                    px: 1.5,
                    py: 0.25,
                    borderRadius: 1,
                  }}
                >
                  {(confidenceThreshold * 100).toFixed(0)}%
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Minimum confidence level required for detections
              </Typography>
              <Slider
                value={confidenceThreshold}
                onChange={(_, value) => setConfidenceThreshold(value as number)}
                min={0}
                max={1}
                step={0.05}
                valueLabelDisplay="auto"
                valueLabelFormat={(value) => `${(value * 100).toFixed(0)}%`}
                sx={{
                  '& .MuiSlider-thumb': {
                    backgroundColor: theme.palette.primary.main,
                  },
                  '& .MuiSlider-track': {
                    background: `linear-gradient(90deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
                  },
                  '& .MuiSlider-rail': {
                    backgroundColor: alpha(theme.palette.primary.main, 0.2),
                  },
                }}
              />
            </Box>

            <Button
              variant="contained"
              onClick={handleSave}
              disabled={!selectedModel || updateMutation.isPending}
              startIcon={<SaveIcon />}
              sx={{ px: 4 }}
            >
              {updateMutation.isPending ? 'Saving...' : 'Save Settings'}
            </Button>
          </CardContent>
        </Card>

        {/* Hardware Detection Card */}
        <Card>
          <CardContent sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    width: 44,
                    height: 44,
                    borderRadius: 2,
                    background: `linear-gradient(135deg, ${alpha(theme.palette.success.main, 0.2)} 0%, ${alpha(theme.palette.success.dark, 0.2)} 100%)`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <HardwareIcon sx={{ color: 'success.main' }} />
                </Box>
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    Hardware Detection
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Auto-detect CPU, platform, and AI accelerators
                  </Typography>
                </Box>
              </Box>
              <Button
                variant="outlined"
                color="success"
                onClick={handleDetectHardware}
                disabled={detectHardwareMutation.isPending}
                startIcon={detectHardwareMutation.isPending ? <CircularProgress size={16} /> : <RefreshIcon />}
                sx={{ minWidth: 120 }}
              >
                {detectHardwareMutation.isPending ? 'Scanning...' : 'Detect'}
              </Button>
            </Box>

            <Divider sx={{ mb: 3 }} />

            {/* Loading State */}
            {(isHardwareLoading || detectHardwareMutation.isPending) && !hardwareData && (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <CircularProgress size={40} sx={{ mb: 2 }} />
                <Typography color="text.secondary">Detecting hardware...</Typography>
              </Box>
            )}

            {/* Error State */}
            {detectHardwareMutation.isError && (
              <Alert severity="error" sx={{ mb: 3 }}>
                Hardware detection failed. Please try again.
              </Alert>
            )}

            {/* Hardware Results */}
            {hardwareData && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {/* CPU Section */}
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <ComputerIcon fontSize="small" color="primary" />
                    <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                      CPU Information
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      p: 2,
                      borderRadius: 2,
                      backgroundColor: alpha(theme.palette.background.default, 0.5),
                      border: `1px solid ${alpha(theme.palette.divider, 0.3)}`,
                    }}
                  >
                    <Box
                      sx={{
                        display: 'grid',
                        gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
                        gap: 2,
                      }}
                    >
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Architecture
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {formatArchitecture(hardwareData.cpu.architecture)}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Vendor
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {hardwareData.cpu.vendor}
                        </Typography>
                      </Box>
                      <Box sx={{ gridColumn: { xs: '1', sm: '1 / -1' } }}>
                        <Typography variant="caption" color="text.secondary">
                          Model
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500, wordBreak: 'break-word' }}>
                          {hardwareData.cpu.model_name}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Cores / Threads
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {hardwareData.cpu.cores} / {hardwareData.cpu.threads}
                        </Typography>
                      </Box>
                      {hardwareData.cpu.max_frequency_mhz && (
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            Max Frequency
                          </Typography>
                          <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            {(hardwareData.cpu.max_frequency_mhz / 1000).toFixed(2)} GHz
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  </Box>
                </Box>

                {/* Platform Section */}
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <StorageIcon fontSize="small" color="secondary" />
                    <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                      Platform Information
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      p: 2,
                      borderRadius: 2,
                      backgroundColor: alpha(theme.palette.background.default, 0.5),
                      border: `1px solid ${alpha(theme.palette.divider, 0.3)}`,
                    }}
                  >
                    <Box
                      sx={{
                        display: 'grid',
                        gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
                        gap: 2,
                      }}
                    >
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Vendor
                        </Typography>
                        <Chip
                          label={formatPlatformVendor(hardwareData.platform.vendor)}
                          size="small"
                          color="primary"
                          variant="outlined"
                        />
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Board
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {hardwareData.platform.board_name}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          OS
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {hardwareData.platform.os_name} {hardwareData.platform.os_version}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Kernel
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {hardwareData.platform.kernel_version}
                        </Typography>
                      </Box>
                    </Box>
                  </Box>
                </Box>

                {/* Memory Section */}
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <MemoryIcon fontSize="small" color="info" />
                    <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                      Memory
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      p: 2,
                      borderRadius: 2,
                      backgroundColor: alpha(theme.palette.background.default, 0.5),
                      border: `1px solid ${alpha(theme.palette.divider, 0.3)}`,
                    }}
                  >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">
                        {hardwareData.memory.available_gb.toFixed(1)} GB available of{' '}
                        {hardwareData.memory.total_gb.toFixed(1)} GB
                      </Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600, color: 'primary.main' }}>
                        {hardwareData.memory.used_percent.toFixed(1)}% used
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={hardwareData.memory.used_percent}
                      sx={{
                        height: 8,
                        borderRadius: 4,
                        backgroundColor: alpha(theme.palette.primary.main, 0.2),
                        '& .MuiLinearProgress-bar': {
                          borderRadius: 4,
                          background:
                            hardwareData.memory.used_percent > 80
                              ? `linear-gradient(90deg, ${theme.palette.warning.main} 0%, ${theme.palette.error.main} 100%)`
                              : `linear-gradient(90deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
                        },
                      }}
                    />
                  </Box>
                </Box>

                {/* Accelerators Section */}
                <Box>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      mb: 2,
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <SpeedIcon fontSize="small" color="warning" />
                      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                        AI Accelerators
                      </Typography>
                    </Box>
                    {hardwareData.recommended_accelerator && (
                      <Chip
                        label={`Recommended: ${formatAcceleratorName(hardwareData.recommended_accelerator)}`}
                        size="small"
                        color="success"
                        icon={<CheckCircleIcon />}
                      />
                    )}
                  </Box>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    {hardwareData.accelerators.map((acc, index) => (
                      <Box
                        key={`${acc.type}-${index}`}
                        sx={{
                          p: 2,
                          borderRadius: 2,
                          backgroundColor:
                            acc.status === 'available'
                              ? alpha(theme.palette.success.main, 0.1)
                              : alpha(theme.palette.background.default, 0.5),
                          border: `1px solid ${
                            acc.status === 'available'
                              ? alpha(theme.palette.success.main, 0.3)
                              : alpha(theme.palette.divider, 0.3)
                          }`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          flexWrap: 'wrap',
                          gap: 1,
                        }}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                          <Typography sx={{ fontSize: '1.2rem' }}>{getAcceleratorIcon(acc.type)}</Typography>
                          <Box>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                              {acc.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {formatAcceleratorName(acc.type)}
                              {acc.memory_mb && ` • ${(acc.memory_mb / 1024).toFixed(1)} GB VRAM`}
                              {acc.driver_version && ` • Driver ${acc.driver_version}`}
                            </Typography>
                          </Box>
                        </Box>
                        <Tooltip title={acc.status === 'driver_missing' ? 'Driver not installed' : acc.status}>
                          <Chip
                            label={acc.status.replace('_', ' ')}
                            size="small"
                            color={getStatusColor(acc.status) as 'success' | 'warning' | 'error' | 'default'}
                            icon={getStatusIcon(acc.status)}
                            sx={{ textTransform: 'capitalize' }}
                          />
                        </Tooltip>
                      </Box>
                    ))}
                  </Box>
                </Box>

                {/* Detection Info */}
                <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'right' }}>
                  Detection completed in {hardwareData.detection_duration_ms.toFixed(0)}ms • Last updated:{' '}
                  {new Date(hardwareData.detection_timestamp).toLocaleString()}
                </Typography>
              </Box>
            )}

            {/* Initial State - No Data */}
            {!hardwareData && !isHardwareLoading && !detectHardwareMutation.isPending && (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <HardwareIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                <Typography color="text.secondary" sx={{ mb: 1 }}>
                  Hardware not yet detected
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Click "Detect" to scan for CPU, platform, and AI accelerators
                </Typography>
              </Box>
            )}
          </CardContent>
        </Card>

        {/* System Info Card */}
        <Card>
          <CardContent sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
              <Box
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: 2,
                  background: `linear-gradient(135deg, ${alpha(theme.palette.secondary.main, 0.2)} 0%, ${alpha(theme.palette.secondary.dark, 0.2)} 100%)`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <SettingsIcon sx={{ color: 'secondary.main' }} />
              </Box>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  System Information
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  CARCARA-NVC application details
                </Typography>
              </Box>
            </Box>

            <Divider sx={{ mb: 3 }} />

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">
                  Product Name
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 600, color: 'primary.main' }}>
                  CARCARA-NVC
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">
                  Description
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                  Network Video Controller
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">
                  Version
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                  1.0.0
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Box>
  )
}

export default Settings
