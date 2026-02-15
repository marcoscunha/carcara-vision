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
  Skeleton,
  Divider,
  Chip,
  CircularProgress,
  Alert,
  Tooltip,
  LinearProgress,
  Avatar,
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
  Person as PersonIcon,
  Logout as LogoutIcon,
  AdminPanelSettings as AdminIcon,
  OpenInNew as OpenInNewIcon,
} from '@mui/icons-material'
import { useModels, useUpdateModel, useHardwareDetection, useDetectHardware } from '../hooks/useQueries'
import { useAuth } from '../auth'
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

  // Auth hook for user info
  const { user, logout, isAdmin } = useAuth()

  const keycloakBaseUrl = import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8280'
  const keycloakRealm = import.meta.env.VITE_KEYCLOAK_REALM || 'carcara'
  const keycloakAdminUrl = `${keycloakBaseUrl}/admin/master/console/#/realms/${keycloakRealm}/users`

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
        <Skeleton variant="text" width={120} height={40} className="loading-skeleton" />
        <Skeleton variant="rounded" height={300} />
      </Box>
    )
  }

  const modelList = models?.data || []

  return (
    <Box className="fade-in">
      {/* Page Header */}
      <Box className="page-header">
        <Box>
          <Typography variant="h4" className="page-header__title">
            Settings
          </Typography>
          <Typography variant="body2" color="text.secondary" className="page-header__subtitle">
            Configure system and detection parameters
          </Typography>
        </Box>
      </Box>

      {/* Settings Cards */}
      <Box className="settings-grid">
        {/* Object Detection Settings */}
        <Card>
          <CardContent className="settings-card__content">
            <Box className="settings-card__header">
              <Box className="settings-card__icon settings-card__icon--primary">
                <MemoryIcon color="primary" />
              </Box>
              <Box>
                <Typography variant="h6" className="settings-card__title">
                  Object Detection
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Configure AI model and detection sensitivity
                </Typography>
              </Box>
            </Box>

            <Divider className="settings-card__divider" />

            <FormControl fullWidth className="settings-card__control">
              <InputLabel>Detection Model</InputLabel>
              <Select value={selectedModel} label="Detection Model" onChange={(e) => setSelectedModel(e.target.value)}>
                {modelList.map((model: Model) => (
                  <MenuItem key={model.name} value={model.name}>
                    {model.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box className="settings-card__metric">
              <Box className="settings-card__metric-header">
                <Typography className="settings-card__metric-label">Confidence Threshold</Typography>
                <Typography className="settings-card__metric-value">
                  {(confidenceThreshold * 100).toFixed(0)}%
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" className="settings-card__metric-note">
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
                className="settings-card__slider"
              />
            </Box>

            <Button
              variant="contained"
              onClick={handleSave}
              disabled={!selectedModel || updateMutation.isPending}
              startIcon={<SaveIcon />}
              className="settings-card__save"
            >
              {updateMutation.isPending ? 'Saving...' : 'Save Settings'}
            </Button>
          </CardContent>
        </Card>

        {/* Hardware Detection Card */}
        <Card>
          <CardContent className="settings-card__content">
            <Box className="settings-card__header settings-card__header--space">
              <Box className="settings-card__header-left">
                <Box className="settings-card__icon settings-card__icon--success">
                  <HardwareIcon color="success" />
                </Box>
                <Box>
                  <Typography variant="h6" className="settings-card__title">
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
                className="settings-card__detect"
              >
                {detectHardwareMutation.isPending ? 'Scanning...' : 'Detect'}
              </Button>
            </Box>

            <Divider className="settings-card__divider" />

            {/* Loading State */}
            {(isHardwareLoading || detectHardwareMutation.isPending) && !hardwareData && (
              <Box className="settings-card__loading">
                <CircularProgress size={40} className="settings-card__loading-icon" />
                <Typography color="text.secondary">Detecting hardware...</Typography>
              </Box>
            )}

            {/* Error State */}
            {detectHardwareMutation.isError && (
              <Alert severity="error" className="settings-card__alert">
                Hardware detection failed. Please try again.
              </Alert>
            )}

            {/* Hardware Results */}
            {hardwareData && (
              <Box className="settings-sections">
                {/* CPU Section */}
                <Box>
                  <Box className="settings-section__header">
                    <ComputerIcon fontSize="small" color="primary" />
                    <Typography variant="subtitle2" className="settings-section__title">
                      CPU Information
                    </Typography>
                  </Box>
                  <Box className="settings-panel">
                    <Box className="settings-panel__grid">
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Architecture
                        </Typography>
                        <Typography variant="body2" className="text-strong">
                          {formatArchitecture(hardwareData.cpu.architecture)}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Vendor
                        </Typography>
                        <Typography variant="body2" className="text-strong">
                          {hardwareData.cpu.vendor}
                        </Typography>
                      </Box>
                      <Box className="settings-panel__full">
                        <Typography variant="caption" color="text.secondary">
                          Model
                        </Typography>
                        <Typography variant="body2" className="text-strong text-break">
                          {hardwareData.cpu.model_name}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Cores / Threads
                        </Typography>
                        <Typography variant="body2" className="text-strong">
                          {hardwareData.cpu.cores} / {hardwareData.cpu.threads}
                        </Typography>
                      </Box>
                      {hardwareData.cpu.max_frequency_mhz && (
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            Max Frequency
                          </Typography>
                          <Typography variant="body2" className="text-strong">
                            {(hardwareData.cpu.max_frequency_mhz / 1000).toFixed(2)} GHz
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  </Box>
                </Box>

                {/* Platform Section */}
                <Box>
                  <Box className="settings-section__header">
                    <StorageIcon fontSize="small" color="secondary" />
                    <Typography variant="subtitle2" className="settings-section__title">
                      Platform Information
                    </Typography>
                  </Box>
                  <Box className="settings-panel">
                    <Box className="settings-panel__grid">
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
                        <Typography variant="body2" className="text-strong">
                          {hardwareData.platform.board_name}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          OS
                        </Typography>
                        <Typography variant="body2" className="text-strong">
                          {hardwareData.platform.os_name} {hardwareData.platform.os_version}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Kernel
                        </Typography>
                        <Typography variant="body2" className="text-strong">
                          {hardwareData.platform.kernel_version}
                        </Typography>
                      </Box>
                    </Box>
                  </Box>
                </Box>

                {/* Memory Section */}
                <Box>
                  <Box className="settings-section__header">
                    <MemoryIcon fontSize="small" color="info" />
                    <Typography variant="subtitle2" className="settings-section__title">
                      Memory
                    </Typography>
                  </Box>
                  <Box className="settings-panel">
                    <Box className="settings-panel__row">
                      <Typography variant="body2">
                        {hardwareData.memory.available_gb.toFixed(1)} GB available of{' '}
                        {hardwareData.memory.total_gb.toFixed(1)} GB
                      </Typography>
                      <Typography variant="body2" className="settings-panel__value">
                        {hardwareData.memory.used_percent.toFixed(1)}% used
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={hardwareData.memory.used_percent}
                      className={`settings-panel__progress ${hardwareData.memory.used_percent > 80 ? 'settings-panel__progress--warn' : ''}`}
                    />
                  </Box>
                </Box>

                {/* Accelerators Section */}
                <Box>
                  <Box className="settings-section__header settings-section__header--space">
                    <Box className="settings-section__header-left">
                      <SpeedIcon fontSize="small" color="warning" />
                      <Typography variant="subtitle2" className="settings-section__title">
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
                  <Box className="settings-accel-list">
                    {hardwareData.accelerators.map((acc, index) => (
                      <Box
                        key={`${acc.type}-${index}`}
                        className={`settings-accel-card ${acc.status === 'available' ? 'settings-accel-card--available' : ''}`}
                      >
                        <Box className="settings-accel-card__main">
                          <Typography className="settings-accel-card__icon">{getAcceleratorIcon(acc.type)}</Typography>
                          <Box>
                            <Typography variant="body2" className="settings-accel-card__name">
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
                            className="settings-accel-card__status"
                          />
                        </Tooltip>
                      </Box>
                    ))}
                  </Box>
                </Box>

                {/* Detection Info */}
                <Typography variant="caption" color="text.secondary" className="settings-card__footer-note">
                  Detection completed in {hardwareData.detection_duration_ms.toFixed(0)}ms • Last updated:{' '}
                  {new Date(hardwareData.detection_timestamp).toLocaleString()}
                </Typography>
              </Box>
            )}

            {/* Initial State - No Data */}
            {!hardwareData && !isHardwareLoading && !detectHardwareMutation.isPending && (
              <Box className="settings-card__empty">
                <HardwareIcon className="settings-card__empty-icon" />
                <Typography color="text.secondary" className="settings-card__empty-title">
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
          <CardContent className="settings-card__content">
            <Box className="settings-card__header">
              <Box className="settings-card__icon settings-card__icon--secondary">
                <SettingsIcon color="secondary" />
              </Box>
              <Box>
                <Typography variant="h6" className="settings-card__title">
                  System Information
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  CARCARA-NVC application details
                </Typography>
              </Box>
            </Box>

            <Divider className="settings-card__divider" />

            <Box className="settings-info">
              <Box className="settings-info__row">
                <Typography variant="body2" color="text.secondary">
                  Product Name
                </Typography>
                <Typography variant="body2" className="settings-info__value">
                  CARCARA-NVC
                </Typography>
              </Box>
              <Box className="settings-info__row">
                <Typography variant="body2" color="text.secondary">
                  Description
                </Typography>
                <Typography variant="body2" className="text-strong">
                  Network Video Controller
                </Typography>
              </Box>
              <Box className="settings-info__row">
                <Typography variant="body2" color="text.secondary">
                  Version
                </Typography>
                <Typography variant="body2" className="text-strong">
                  1.0.0
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>

        {/* User Profile Card */}
        <Card>
          <CardContent className="settings-card__content">
            <Box className="settings-card__header">
              <Box className="settings-card__icon settings-card__icon--primary">
                <PersonIcon color="primary" />
              </Box>
              <Box>
                <Typography variant="h6" className="settings-card__title">
                  User Profile
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Your account information
                </Typography>
              </Box>
            </Box>

            <Divider className="settings-card__divider" />

            {user ? (
              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                  <Avatar
                    sx={{
                      width: 56,
                      height: 56,
                      mr: 2,
                      bgcolor: 'primary.main',
                      color: 'primary.contrastText',
                    }}
                  >
                    {user.username.charAt(0).toUpperCase()}
                  </Avatar>
                  <Box>
                    <Typography variant="h6">
                      {user.firstName && user.lastName ? `${user.firstName} ${user.lastName}` : user.username}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {user.email || 'No email'}
                    </Typography>
                  </Box>
                </Box>

                <Box className="settings-info">
                  <Box className="settings-info__row">
                    <Typography variant="body2" color="text.secondary">
                      Username
                    </Typography>
                    <Typography variant="body2" className="settings-info__value">
                      {user.username}
                    </Typography>
                  </Box>
                  <Box className="settings-info__row">
                    <Typography variant="body2" color="text.secondary">
                      Roles
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                      {user.roles.map((role) => (
                        <Chip
                          key={role}
                          label={role}
                          size="small"
                          color={role === 'admin' ? 'primary' : 'default'}
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </Box>
                </Box>

                <Box sx={{ mt: 3 }}>
                  <Button variant="outlined" color="error" startIcon={<LogoutIcon />} onClick={logout} fullWidth>
                    Sign Out
                  </Button>
                </Box>
              </Box>
            ) : (
              <Typography color="text.secondary">Not logged in</Typography>
            )}
          </CardContent>
        </Card>

        {/* User Management Card (Admin Only) */}
        {isAdmin && (
          <Card>
            <CardContent className="settings-card__content">
              <Box className="settings-card__header">
                <Box className="settings-card__icon settings-card__icon--warning">
                  <AdminIcon color="warning" />
                </Box>
                <Box>
                  <Typography variant="h6" className="settings-card__title">
                    User Management
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Manage users via Keycloak Admin Console
                  </Typography>
                </Box>
              </Box>

              <Divider className="settings-card__divider" />

              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Create, edit, and manage user accounts through the Keycloak administration console. You can add new
                users, assign roles, and configure authentication settings.
              </Typography>

              <Button
                variant="outlined"
                color="primary"
                startIcon={<OpenInNewIcon />}
                onClick={() => window.open(keycloakAdminUrl, '_blank', 'noopener,noreferrer')}
                fullWidth
              >
                Open Keycloak Admin Console
              </Button>

              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
                Default credentials: admin / admin
              </Typography>
            </CardContent>
          </Card>
        )}
      </Box>
    </Box>
  )
}

export default Settings
