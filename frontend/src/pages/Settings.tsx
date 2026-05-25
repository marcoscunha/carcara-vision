import React, { useEffect, useMemo, useState } from 'react'
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Skeleton,
  Divider,
  Chip,
  CircularProgress,
  Alert,
  Tooltip,
  LinearProgress,
  Avatar,
  Tab,
  Tabs,
  TextField,
  MenuItem,
} from '@mui/material'
import {
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
  CloudDownload as CloudDownloadIcon,
  AddCircleOutline as AddCircleOutlineIcon,
  DeleteOutline as DeleteOutlineIcon,
  History as HistoryIcon,
  PlayCircleFilled as PlayCircleFilledIcon,
} from '@mui/icons-material'
import {
  useModels,
  useEnsureModel,
  useRegisterModel,
  useDeleteModel,
  useBenchmarkHistory,
  useHardwareDetection,
  useDetectHardware,
  useInferenceRuntimeConfig,
  useRealtimeInferenceMetrics,
  useUpdateInferenceRuntimeConfig,
  useUpdateModel,
} from '../hooks/useQueries'
import { useAuth } from '../auth'
import { AUTH_ENABLED } from '../auth/keycloak'
import type { Model, AcceleratorStatus, AcceleratorType } from '../types'
import { ConfirmDeleteDialog } from '../components/dialogs'

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

// Task type labels for display
const TASK_LABELS: Record<string, string> = {
  detect: 'Detection',
  segment: 'Segmentation',
  pose: 'Pose',
}

const EXECUTED_MODELS_STORAGE_KEY = 'carcara.executedModelsHistory'

const Settings: React.FC = () => {
  const [taskTab, setTaskTab] = useState<string>('detect')
  const [newModelName, setNewModelName] = useState<string>('')
  const [newModelDescription, setNewModelDescription] = useState<string>('')
  const [newModelTaskType, setNewModelTaskType] = useState<string>('detect')
  const [downloadingModels, setDownloadingModels] = useState<string[]>([])
  const [modelPendingDelete, setModelPendingDelete] = useState<string | null>(null)

  // Auth hook for user info
  const { user, logout, isAdmin } = useAuth()

  const keycloakBaseUrl =
    import.meta.env.VITE_KEYCLOAK_URL || `${window.location.protocol}//${window.location.hostname}:8280`
  const keycloakRealm = import.meta.env.VITE_KEYCLOAK_REALM || 'carcara'
  const keycloakAdminUrl = `${keycloakBaseUrl}/admin/master/console/#/realms/${keycloakRealm}/users`

  // TanStack Query hooks
  const { data: allModels, isLoading, refetch: refetchModels } = useModels()
  const { data: benchmarkHistory, isLoading: isBenchmarkHistoryLoading } = useBenchmarkHistory(10)
  const { data: runtimeConfig } = useInferenceRuntimeConfig()
  const { data: realtimeMetrics } = useRealtimeInferenceMetrics()
  const updateRuntimeMutation = useUpdateInferenceRuntimeConfig()
  const updateModelMutation = useUpdateModel()
  const ensureModelMutation = useEnsureModel()
  const deleteModelMutation = useDeleteModel()
  const registerModelMutation = useRegisterModel()

  // Hardware detection hooks
  const { data: hardwareData, isLoading: isHardwareLoading } = useHardwareDetection(true)
  const detectHardwareMutation = useDetectHardware()
  const allModelsList: Model[] = allModels || []
  const [persistedExecutedModelNames, setPersistedExecutedModelNames] = useState<Set<string>>(() => {
    if (typeof window === 'undefined') {
      return new Set<string>()
    }

    try {
      const raw = window.localStorage.getItem(EXECUTED_MODELS_STORAGE_KEY)
      if (!raw) {
        return new Set<string>()
      }

      const parsed = JSON.parse(raw)
      if (!Array.isArray(parsed)) {
        return new Set<string>()
      }

      return new Set<string>(parsed.filter((item): item is string => typeof item === 'string' && item.length > 0))
    } catch {
      return new Set<string>()
    }
  })

  const liveExecutedModelNames = useMemo(() => {
    const names = new Set<string>()
    const perStream = realtimeMetrics?.per_stream || {}

    for (const streamMetrics of Object.values(perStream)) {
      if (streamMetrics.model_name && streamMetrics.samples > 0) {
        names.add(streamMetrics.model_name)
      }
    }

    return names
  }, [realtimeMetrics?.per_stream])

  const displayedExecutedModelNames = useMemo(() => {
    const names = new Set<string>(persistedExecutedModelNames)
    for (const name of liveExecutedModelNames) {
      names.add(name)
    }
    return names
  }, [persistedExecutedModelNames, liveExecutedModelNames])

  useEffect(() => {
    setPersistedExecutedModelNames((previous) => {
      const next = new Set(previous)
      let changed = false

      const benchmarkItems = benchmarkHistory?.items || []
      for (const item of benchmarkItems) {
        if (item.model_name && !next.has(item.model_name)) {
          next.add(item.model_name)
          changed = true
        }
      }

      const perStream = realtimeMetrics?.per_stream || {}
      for (const streamMetrics of Object.values(perStream)) {
        if (streamMetrics.model_name && streamMetrics.samples > 0 && !next.has(streamMetrics.model_name)) {
          next.add(streamMetrics.model_name)
          changed = true
        }
      }

      if (!changed) {
        return previous
      }

      if (typeof window !== 'undefined') {
        window.localStorage.setItem(EXECUTED_MODELS_STORAGE_KEY, JSON.stringify(Array.from(next)))
      }

      return next
    })
  }, [benchmarkHistory?.items, realtimeMetrics?.per_stream])

  const runningModelNames = liveExecutedModelNames

  // Models filtered by current tab (task type)
  const modelList: Model[] = allModelsList.filter((m: Model) => m.task_type === taskTab)
  const downloadedModelsCount = allModelsList.filter((m: Model) => m.is_downloaded).length
  const storageRoots = Array.from(
    new Set(allModelsList.map((m: Model) => m.storage_root).filter((v): v is string => Boolean(v))),
  )

  // Global runtime model selection (default to runtimeConfig or first model)
  const selectedModel = runtimeConfig?.model_name ?? ''
  const selectedTaskType = runtimeConfig?.task_type ?? 'detect'

  useEffect(() => {
    if (downloadingModels.length === 0) {
      return
    }

    const timer = window.setInterval(() => {
      void refetchModels()
    }, 1500)

    return () => {
      window.clearInterval(timer)
    }
  }, [downloadingModels.length, refetchModels])

  useEffect(() => {
    if (downloadingModels.length === 0) {
      return
    }

    setDownloadingModels((current) =>
      current.filter((name) => {
        const model = allModelsList.find((item) => item.name === name)
        return !model?.is_downloaded
      }),
    )
  }, [allModelsList, downloadingModels.length])

  const handleSelectModel = (modelName: string) => {
    updateRuntimeMutation.mutate({ model_name: modelName, task_type: taskTab })
  }

  const handleEnsureModel = (name: string) => {
    setDownloadingModels((current) => (current.includes(name) ? current : [...current, name]))
    ensureModelMutation.mutate(name, {
      onError: () => {
        setDownloadingModels((current) => current.filter((item) => item !== name))
      },
    })
  }

  const handleToggleModelActive = (model: Model) => {
    updateModelMutation.mutate({
      name: model.name,
      data: { is_enabled: !model.is_enabled },
    })
  }

  const handleRequestDeleteModel = (name: string) => {
    setModelPendingDelete(name)
  }

  const handleConfirmDeleteModel = () => {
    if (!modelPendingDelete) {
      return
    }

    const modelToDelete = modelPendingDelete
    deleteModelMutation.mutate(modelToDelete, {
      onSuccess: () => {
        setDownloadingModels((current) => current.filter((item) => item !== modelToDelete))
        setModelPendingDelete(null)
      },
    })
  }

  const handleDetectHardware = () => {
    detectHardwareMutation.mutate(true)
  }

  const handleClearModelHistory = () => {
    setPersistedExecutedModelNames(new Set<string>())
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(EXECUTED_MODELS_STORAGE_KEY)
    }
  }

  const handleRegisterModel = () => {
    const name = newModelName.trim()
    if (!name) {
      return
    }

    registerModelMutation.mutate(
      {
        name,
        task_type: newModelTaskType,
        description: newModelDescription.trim() || undefined,
      },
      {
        onSuccess: () => {
          setNewModelName('')
          setNewModelDescription('')
        },
      },
    )
  }

  if (isLoading) {
    return (
      <Box className="settings-page">
        <Skeleton variant="text" width={120} height={40} className="loading-skeleton" />
        <Skeleton variant="rounded" height={300} />
      </Box>
    )
  }

  return (
    <Box className="fade-in settings-page">
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
                  AI Models
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Configure YOLO models for object detection, pose estimation and segmentation
                </Typography>
              </Box>
            </Box>

            <Divider className="settings-card__divider" />

            {/* Task Type Tabs */}
            <Tabs value={taskTab} onChange={(_, v) => setTaskTab(v)} sx={{ mb: 2 }}>
              <Tab value="detect" label={TASK_LABELS.detect} />
              <Tab value="segment" label={TASK_LABELS.segment} />
              <Tab value="pose" label={TASK_LABELS.pose} />
            </Tabs>

            {/* Global default model indicator */}
            {selectedModel && (
              <Alert severity="info" sx={{ mb: 2 }}>
                <Tooltip title="Fallback model for new streams and streams without an explicit model.">
                  <span>
                    Global default model: <strong>{selectedModel}</strong> (
                    {TASK_LABELS[selectedTaskType] ?? selectedTaskType})
                  </span>
                </Tooltip>
              </Alert>
            )}

            <Alert severity="success" sx={{ mb: 2 }}>
              <Tooltip title="Models with local weights on this device across all task types.">
                <span>
                  Downloaded models: <strong>{downloadedModelsCount}</strong> / {allModelsList.length}
                </span>
              </Tooltip>
            </Alert>

            <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
              <Tooltip title="Clear executed model history icons.">
                <span>
                  <Button
                    size="small"
                    variant="outlined"
                    color="warning"
                    onClick={handleClearModelHistory}
                    disabled={persistedExecutedModelNames.size === 0}
                  >
                    Clear model history
                  </Button>
                </span>
              </Tooltip>
            </Box>

            {storageRoots.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" color="text.secondary">
                  Model storage location
                </Typography>
                <Box sx={{ mt: 0.5, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  {storageRoots.map((root) => (
                    <Chip key={root} label={root} size="small" variant="outlined" sx={{ maxWidth: '100%' }} />
                  ))}
                </Box>
              </Box>
            )}

            {/* Model list for active tab */}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {modelList.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                  No models found for {TASK_LABELS[taskTab]}
                </Typography>
              ) : (
                modelList.map((model: Model) => (
                  <Box
                    key={model.name}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      p: 1.5,
                      borderRadius: 1,
                      border: '1px solid',
                      borderColor: model.name === selectedModel ? 'primary.main' : 'divider',
                      bgcolor: model.name === selectedModel ? 'primary.50' : 'transparent',
                      gap: 1,
                    }}
                  >
                    {(() => {
                      const isDownloading = downloadingModels.includes(model.name)
                      const isDeleting = deleteModelMutation.isPending && deleteModelMutation.variables === model.name
                      const hasExecutedOnHardware = displayedExecutedModelNames.has(model.name)
                      const isRunningOnAnyStream = runningModelNames.has(model.name)

                      return (
                        <>
                          {/* Model info */}
                          <Box sx={{ flex: 1, minWidth: 0 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                              <Typography variant="body2" fontWeight={600} noWrap>
                                {model.name}
                              </Typography>
                              {hasExecutedOnHardware && (
                                <Tooltip title="This model has run on this hardware before.">
                                  <HistoryIcon fontSize="small" color="action" />
                                </Tooltip>
                              )}
                              {isRunningOnAnyStream && (
                                <Tooltip title="This model is running on at least one stream now.">
                                  <PlayCircleFilledIcon fontSize="small" color="success" />
                                </Tooltip>
                              )}
                            </Box>
                            <Typography variant="caption" color="text.secondary">
                              {model.description || model.task_type}
                            </Typography>
                            {model.storage_path && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ display: 'block', mt: 0.25, wordBreak: 'break-all' }}
                              >
                                Stored at: {model.storage_path}
                              </Typography>
                            )}
                            {isDownloading && (
                              <Box sx={{ mt: 1 }}>
                                <LinearProgress />
                                <Typography variant="caption" color="text.secondary">
                                  Download in progress...
                                </Typography>
                              </Box>
                            )}
                          </Box>

                          {/* Status chip */}
                          <Tooltip
                            title={
                              isDownloading
                                ? 'Weights are downloading now.'
                                : model.is_downloaded
                                  ? model.is_enabled
                                    ? 'Downloaded and selectable in stream model fields.'
                                    : 'Downloaded but hidden from stream model fields.'
                                  : 'Not downloaded on this device.'
                            }
                          >
                            <Chip
                              label={
                                isDownloading
                                  ? 'Downloading'
                                  : model.is_downloaded
                                    ? model.is_enabled
                                      ? 'Downloaded • Active'
                                      : 'Downloaded • Inactive'
                                    : 'Not downloaded'
                              }
                              size="small"
                              color={
                                isDownloading
                                  ? 'warning'
                                  : model.is_downloaded
                                    ? model.is_enabled
                                      ? 'success'
                                      : 'default'
                                    : 'default'
                              }
                              variant="outlined"
                            />
                          </Tooltip>

                          {/* Actions */}
                          <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                            {/* Download / ensure button */}
                            {!model.is_downloaded && (
                              <Tooltip title="Download weights to this device.">
                                <span>
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    startIcon={isDownloading ? <CircularProgress size={14} /> : <CloudDownloadIcon />}
                                    onClick={() => handleEnsureModel(model.name)}
                                    disabled={isDownloading}
                                  >
                                    Download model
                                  </Button>
                                </span>
                              </Tooltip>
                            )}

                            {/* Set as global model */}
                            {model.is_downloaded && model.name !== selectedModel && (
                              <Tooltip title="Set as the global default model.">
                                <span>
                                  <Button
                                    size="small"
                                    variant="contained"
                                    onClick={() => handleSelectModel(model.name)}
                                    disabled={updateRuntimeMutation.isPending || isDeleting || isDownloading}
                                  >
                                    Set as default
                                  </Button>
                                </span>
                              </Tooltip>
                            )}

                            {model.name === selectedModel && (
                              <Tooltip title="Current global default model.">
                                <Chip label="Default" size="small" color="primary" icon={<CheckCircleIcon />} />
                              </Tooltip>
                            )}

                            {model.is_downloaded && (
                              <Tooltip
                                title={
                                  model.is_enabled
                                    ? 'Disable this model in stream model selectors.'
                                    : 'Enable this model in stream model selectors.'
                                }
                              >
                                <span>
                                  <Button
                                    size="small"
                                    variant={model.is_enabled ? 'outlined' : 'contained'}
                                    color={model.is_enabled ? 'warning' : 'success'}
                                    onClick={() => handleToggleModelActive(model)}
                                    disabled={updateModelMutation.isPending || isDeleting || isDownloading}
                                  >
                                    {model.is_enabled ? 'Disable model' : 'Enable model'}
                                  </Button>
                                </span>
                              </Tooltip>
                            )}

                            {model.is_downloaded && (
                              <Tooltip
                                title={
                                  model.name === selectedModel
                                    ? 'Cannot delete the current default model.'
                                    : 'Delete local weights for this model.'
                                }
                              >
                                <span>
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    color="error"
                                    startIcon={isDeleting ? <CircularProgress size={14} /> : <DeleteOutlineIcon />}
                                    onClick={() => handleRequestDeleteModel(model.name)}
                                    disabled={model.name === selectedModel || isDeleting || isDownloading}
                                  >
                                    Delete model
                                  </Button>
                                </span>
                              </Tooltip>
                            )}
                          </Box>
                        </>
                      )
                    })()}
                  </Box>
                ))
              )}
            </Box>

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Add New Model
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1, mb: 1 }}>
              <TextField
                size="small"
                label="Model Name"
                placeholder="my-yolo-model"
                value={newModelName}
                onChange={(event) => setNewModelName(event.target.value)}
                fullWidth
              />
              <TextField
                size="small"
                label="Task Type"
                select
                value={newModelTaskType}
                onChange={(event) => setNewModelTaskType(event.target.value)}
                fullWidth
              >
                {Object.entries(TASK_LABELS).map(([key, label]) => (
                  <MenuItem key={key} value={key}>
                    {label}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                size="small"
                label="Description"
                placeholder="Optional"
                value={newModelDescription}
                onChange={(event) => setNewModelDescription(event.target.value)}
                fullWidth
                sx={{ gridColumn: { xs: '1', sm: '1 / span 2' } }}
              />
            </Box>
            <Button
              size="small"
              variant="outlined"
              startIcon={<AddCircleOutlineIcon />}
              onClick={handleRegisterModel}
              disabled={registerModelMutation.isPending || !newModelName.trim()}
            >
              {registerModelMutation.isPending ? 'Adding model...' : 'Add model to catalog'}
            </Button>
            {registerModelMutation.isError && (
              <Alert severity="error" sx={{ mt: 1 }}>
                Failed to add model. Please check the model name and try again.
              </Alert>
            )}

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Previous Benchmark Reports
            </Typography>
            {isBenchmarkHistoryLoading ? (
              <Typography variant="body2" color="text.secondary">
                Loading benchmark history...
              </Typography>
            ) : benchmarkHistory && benchmarkHistory.items.length > 0 ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                {benchmarkHistory.items.slice(0, 5).map((item) => (
                  <Box
                    key={item.run_id}
                    sx={{
                      p: 1,
                      borderRadius: 1,
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Typography variant="body2" fontWeight={600}>
                      {item.scenario_name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      Run: {item.run_id}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      Model: {item.model_name || 'n/a'} • Streams: {item.streams_count}
                    </Typography>
                    {item.created_at && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        Created: {new Date(item.created_at).toLocaleString()}
                      </Typography>
                    )}
                  </Box>
                ))}
                <Typography variant="caption" color="text.secondary">
                  Reports folder: {benchmarkHistory.reports_dir}
                </Typography>
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No benchmark reports found yet.
              </Typography>
            )}
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
                        <Tooltip
                          title={
                            acc.status === 'driver_missing'
                              ? 'Driver is not installed.'
                              : `Status is ${acc.status.replace('_', ' ')}.`
                          }
                        >
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
                  Carcara Vision application details
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
                  Carcara Vision
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

        {/* User Profile Card (only when Keycloak auth is enabled) */}
        {AUTH_ENABLED && user && (
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

              {user && (
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
              )}
            </CardContent>
          </Card>
        )}

        {/* User Management Card (Admin Only, when Keycloak auth is enabled) */}
        {AUTH_ENABLED && isAdmin && (
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
            </CardContent>
          </Card>
        )}
      </Box>

      <ConfirmDeleteDialog
        open={Boolean(modelPendingDelete)}
        onClose={() => setModelPendingDelete(null)}
        onConfirm={handleConfirmDeleteModel}
        title="Delete Model"
        itemName={modelPendingDelete || ''}
        warningMessage="This removes local model files from this hardware. You can download the model again later from Settings."
        isLoading={deleteModelMutation.isPending}
      />
    </Box>
  )
}

export default Settings
