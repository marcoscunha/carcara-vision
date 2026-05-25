import axios from 'axios'
import {
  Camera,
  Stream,
  StreamCreate,
  Detection,
  Alarm,
  AlarmCreate,
  AlarmZone,
  AlarmZoneCreate,
  AlarmEvent,
  Model,
  RegionOfInterest,
  StreamURLs,
  HardwareDetectionResult,
  AcceleratorInfo,
  DiscoveredCamera,
  DiscoveryProtocol,
  InferenceRuntimeConfig,
  RealtimeInferenceMetrics,
  BenchmarkScenario,
  BenchmarkExportResponse,
  BenchmarkHistoryResponse,
  ModelRegistrationPayload,
} from '../types'
import keycloak from '../auth/keycloak'
import { AUTH_ENABLED } from '../auth/keycloak'
import { getApiBaseUrl } from '../utils/apiUrl'

const API_URL = getApiBaseUrl()

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * Request interceptor to add authentication token.
 * Automatically refreshes token if it's about to expire.
 */
api.interceptors.request.use(
  async (config) => {
    if (!AUTH_ENABLED) {
      return config
    }

    if (keycloak.authenticated && keycloak.token) {
      // Refresh token if it expires within 30 seconds
      try {
        await keycloak.updateToken(30)
      } catch (error) {
        console.error('Token refresh failed:', error)
        // Token refresh failed, redirect to login
        keycloak.login()
        return Promise.reject(new Error('Token refresh failed'))
      }

      // Add Authorization header
      config.headers.Authorization = `Bearer ${keycloak.token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

/**
 * Response interceptor to handle authentication errors.
 * Redirects to login on 401 Unauthorized responses.
 */
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (!AUTH_ENABLED) {
      return Promise.reject(error)
    }

    if (error.response?.status === 401) {
      // Session expired or invalid token
      console.log('Received 401, redirecting to login')
      keycloak.login()
    }
    return Promise.reject(error)
  },
)

export interface CameraInfo {
  device_id: number
  device_path: string
  physical_address?: string
  usb_id?: string
  name: string
  friendly_name?: string
  resolution: [number, number]
  fps: number
  is_available: boolean
  supported_resolutions: [number, number][]
}

export interface ApiResponse<T> {
  data: T
}

// Camera endpoints
export const cameraApi = {
  getAll: async () => {
    const response = await api.get<ApiResponse<Camera[]>>('/cameras/')
    return response.data
  },
  get: (id: number) => api.get<Camera>(`/cameras/${id}`),
  create: (camera: Partial<Camera>) => api.post<Camera>('/cameras/', camera),
  update: (id: number, camera: Partial<Camera>) => api.put<Camera>(`/cameras/${id}`, camera),
  delete: (id: number) => api.delete(`/cameras/${id}`),
  scan: () => api.get<CameraInfo[]>('/cameras/scan'),
}

// Stream endpoints
export const streamApi = {
  getAll: async (status?: string) => {
    const params = status ? { status } : {}
    const response = await api.get<ApiResponse<Stream[]>>('/streams/', { params })
    return response.data
  },
  getById: (id: number) => api.get<Stream>(`/streams/${id}`),
  getUrls: (id: number) => api.get<StreamURLs>(`/streams/${id}/urls`),
  create: (data: StreamCreate) => api.post<Stream>('/streams/', data),
  update: (id: number, data: Partial<Stream>) => api.put<Stream>(`/streams/${id}`, data),
  delete: (id: number) => api.delete(`/streams/${id}`),
  restart: (id: number) => api.post<Stream>(`/streams/${id}/restart`),
  reorder: (ordered_ids: number[]) => api.post<Stream[]>('/streams/reorder', { ordered_ids }),
  getRealtimeMetrics: () => api.get<RealtimeInferenceMetrics>('/streams/metrics/realtime'),
  getStreamMetrics: (id: number) => api.get(`/streams/${id}/metrics`),
  getBenchmarkScenarioTemplate: () => api.get<BenchmarkScenario>('/streams/metrics/benchmark/scenario-template'),
  exportBenchmarkMetrics: (scenario: BenchmarkScenario) =>
    api.post<BenchmarkExportResponse>('/streams/metrics/benchmark/export', scenario),
  getBenchmarkHistory: (limit: number = 20) =>
    api.get<BenchmarkHistoryResponse>('/streams/metrics/benchmark/history', { params: { limit } }),
  checkHealth: () => api.get('/streams/health/gstreamer'),
}

// Detection endpoints
export const detectionApi = {
  getAll: async (params?: { camera_id?: number; stream_id?: number }) => {
    const response = await api.get<ApiResponse<Detection[]>>('/detections', { params })
    return response.data
  },
  getById: (id: number) => api.get<Detection>(`/detections/${id}`),
  create: (data: Omit<Detection, 'id' | 'timestamp'>) => api.post<Detection>('/detections', data),
  delete: (id: number) => api.delete(`/detections/${id}`),
}

// Alarm endpoints
export const alarmApi = {
  getAll: async (stream_id?: number) => {
    const params = stream_id ? { stream_id } : {}
    const response = await api.get<ApiResponse<Alarm[]>>('/alarms', { params })
    return response.data
  },
  getById: (id: number) => api.get<Alarm>(`/alarms/${id}`),
  create: (data: AlarmCreate) => api.post<Alarm>('/alarms', data),
  update: (id: number, data: Partial<AlarmCreate>) => api.put<Alarm>(`/alarms/${id}`, data),
  delete: (id: number) => api.delete(`/alarms/${id}`),
}

// Alarm zone endpoints
export const alarmZoneApi = {
  getAll: async (stream_id: number) => {
    const response = await api.get<ApiResponse<AlarmZone[]>>('/alarms/zones', { params: { stream_id } })
    return response.data
  },
  create: (data: AlarmZoneCreate) => api.post<AlarmZone>('/alarms/zones', data),
  delete: (id: number) => api.delete(`/alarms/zones/${id}`),
}

// Alarm event endpoints
export const alarmEventApi = {
  getAll: async (params?: {
    alarm_id?: number
    stream_id?: number
    state?: string
    limit?: number
    offset?: number
  }) => {
    const response = await api.get<ApiResponse<AlarmEvent[]>>('/alarms/events', { params })
    return response.data
  },
  getById: (id: number) => api.get<AlarmEvent>(`/alarms/events/${id}`),
  ack: (id: number, notes?: string) => api.post<AlarmEvent>(`/alarms/events/${id}/ack`, { notes }),
  delete: (id: number) => api.delete(`/alarms/events/${id}`),
}

// Model endpoints
export const modelApi = {
  getAll: async (task_type?: string) => {
    const params = task_type ? { task_type } : {}
    const response = await api.get<Model[] | ApiResponse<Model[]>>('/models/', { params })
    const payload = response.data as Model[] | ApiResponse<Model[]>
    return Array.isArray(payload) ? payload : payload.data
  },
  getById: (name: string) => api.get<Model>(`/models/${name}`),
  update: (name: string, data: Partial<Model>) => api.put<Model>(`/models/${name}`, data),
  ensure: (name: string) => api.post<{ status: string; name: string }>(`/models/${name}/ensure`),
  delete: (name: string) =>
    api.delete<{ name: string; removed_files: string[]; is_downloaded: boolean }>(`/models/${name}`),
  register: (data: ModelRegistrationPayload) => api.post<Model>('/models/catalog/register', data),
}

// Region of Interest endpoints
export const roiApi = {
  getAll: async (camera_id: number) => {
    const response = await api.get<ApiResponse<RegionOfInterest[]>>('/roi', {
      params: { camera_id },
    })
    return response.data
  },
  getById: (id: number) => api.get<RegionOfInterest>(`/roi/${id}`),
  create: (data: Omit<RegionOfInterest, 'id' | 'created_at' | 'updated_at'>) =>
    api.post<RegionOfInterest>('/roi', data),
  update: (id: number, data: Partial<RegionOfInterest>) => api.put<RegionOfInterest>(`/roi/${id}`, data),
  delete: (id: number) => api.delete(`/roi/${id}`),
}

// Hardware Detection endpoints
export const hardwareApi = {
  detect: async (refresh: boolean = false) => {
    const response = await api.get<HardwareDetectionResult>('/hardware/detect', {
      params: { refresh },
    })
    return response.data
  },
  getCpu: async () => {
    const response = await api.get<HardwareDetectionResult['cpu']>('/hardware/cpu')
    return response.data
  },
  getPlatform: async () => {
    const response = await api.get<HardwareDetectionResult['platform']>('/hardware/platform')
    return response.data
  },
  getAccelerators: async (refresh: boolean = false) => {
    const response = await api.get<AcceleratorInfo[]>('/hardware/accelerators', {
      params: { refresh },
    })
    return response.data
  },
  getRecommended: async () => {
    const response = await api.get<{ recommended: string; available_accelerators: string[] }>('/hardware/recommended')
    return response.data
  },
}

// Discovery endpoints (IP camera scanning)
export const discoveryApi = {
  scanCameras: async (protocol: DiscoveryProtocol = 'mdns', timeout: number = 3.0) => {
    const response = await api.get<DiscoveredCamera[]>('/discovery/cameras', {
      params: { protocol, timeout },
    })
    return response.data
  },
}

// Inference runtime endpoints (system-wide model + accelerator)
export const inferenceRuntimeApi = {
  getConfig: async () => {
    const response = await api.get<InferenceRuntimeConfig>('/inference-runtime/')
    return response.data
  },
  updateConfig: (data: Partial<Pick<InferenceRuntimeConfig, 'model_name' | 'accelerator' | 'task_type'>>) =>
    api.put<InferenceRuntimeConfig>('/inference-runtime/', data),
}
