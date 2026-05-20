export interface Camera {
  id: number
  name: string
  rtsp_url: string | null
  is_active: boolean
  device_id: number
  device_path: string | null
  resolution: [number, number]
  fps: number
  is_available: boolean
  camera_type: string
  created_at: string
  updated_at: string
}

export interface StreamURLs {
  rtsp: string
  webrtc: string
  hls: string
  mse: string
  mjpeg: string
  ws: string
  // Annotated stream (server-side AI overlay)
  annotated_rtsp?: string
  annotated_webrtc?: string
  annotated_hls?: string
  annotated_mse?: string
  annotated_mjpeg?: string
}

export interface Stream {
  id: number
  camera_id: number
  stream_name: string
  status: string
  current_frame: number
  urls: StreamURLs | null
  worker_active?: boolean
  stream_metadata: Record<string, any>
  detection_enabled?: boolean
  detection_model?: string
  detection_task_type?: string
  detection_confidence?: number
  detection_classes?: number[] | null
  sync_video_predictions?: boolean
  created_at: string
  updated_at: string
}

export interface StreamCreate {
  camera_id: number
  width?: number
  height?: number
  codec?: string
  detection_enabled?: boolean
  detection_model?: string
  detection_task_type?: string
  detection_confidence?: number
  detection_classes?: number[] | null
  sync_video_predictions?: boolean
  stream_metadata?: Record<string, any>
}

export interface InferenceRuntimeConfig {
  model_name: string
  accelerator: string
  task_type: string
  available_models: string[]
  available_accelerators: string[]
  available_task_types: string[]
}

export interface StreamInferenceMetrics {
  stream_id: number
  samples: number
  avg_inference_time_ms: number
  min_inference_time_ms: number
  max_inference_time_ms: number
  fps: number
  inference_throughput_fps: number
  target_inference_fps: number
  output_fps: number
  last_inference_time_ms: number
  model_name: string | null
  accelerator: string | null
}

export interface RealtimeInferenceMetrics {
  global: {
    samples: number
    avg_inference_time_ms: number
    min_inference_time_ms: number
    max_inference_time_ms: number
    fps: number
  }
  per_stream: Record<number, StreamInferenceMetrics>
}

export interface BenchmarkScenario {
  scenario_name: string
  duration_seconds: number
  stream_count: number
  resolution: string
  model_name: string
  annotation_enabled: boolean
  notes?: string | null
}

export interface BenchmarkExportResponse {
  run_id: string
  json_report_path: string
  csv_report_path: string
  scenario_name: string
  streams_count: number
}

export interface Detection {
  id: number
  camera_id: number
  stream_id: number
  frame_number: number
  timestamp: string
  model_name: string
  confidence: number
  class_name: string
  bbox: number[]
  metadata: Record<string, any>
}

export interface Alarm {
  id: number
  name: string
  camera_id: number
  class_name: string
  confidence_threshold: number
  region_of_interest: number[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Model {
  name: string
  description: string
  is_available: boolean
  is_downloaded: boolean
  task_type: string
  confidence_threshold: number
}

export interface RegionOfInterest {
  id: number
  name: string
  camera_id: number
  points: number[][]
  created_at: string
  updated_at: string
}

// ============================================================================
// Hardware Detection Types
// ============================================================================

export type CPUArchitecture = 'x86_64' | 'x86' | 'arm64' | 'armv7' | 'armv8' | 'unknown'

export type PlatformVendor =
  | 'intel'
  | 'amd'
  | 'nvidia_jetson'
  | 'raspberry_pi'
  | 'orange_pi'
  | 'aetina'
  | 'rock_pi'
  | 'khadas'
  | 'generic_arm'
  | 'generic_x86'
  | 'unknown'

export type AcceleratorType =
  | 'nvidia_gpu'
  | 'nvidia_tensorrt'
  | 'nvidia_jetson'
  | 'google_coral_usb'
  | 'google_coral_pcie'
  | 'google_coral_m2'
  | 'hailo_8'
  | 'hailo_8l'
  | 'hailo_10'
  | 'intel_openvino'
  | 'intel_movidius'
  | 'axelera_m2'
  | 'amd_rocm'
  | 'cpu'

export type AcceleratorStatus = 'available' | 'unavailable' | 'driver_missing' | 'not_detected' | 'error'

export interface CPUInfo {
  architecture: CPUArchitecture
  model_name: string
  vendor: string
  cores: number
  threads: number
  max_frequency_mhz?: number
  features: string[]
}

export interface MemoryInfo {
  total_gb: number
  available_gb: number
  used_percent: number
}

export interface PlatformInfo {
  vendor: PlatformVendor
  board_name: string
  board_model?: string
  serial_number?: string
  os_name: string
  os_version: string
  kernel_version: string
}

export interface AcceleratorInfo {
  type: AcceleratorType
  name: string
  status: AcceleratorStatus
  driver_version?: string
  firmware_version?: string
  memory_mb?: number
  compute_capability?: string
  device_path?: string
  pcie_address?: string
  details: Record<string, unknown>
}

export interface HardwareDetectionResult {
  cpu: CPUInfo
  memory: MemoryInfo
  platform: PlatformInfo
  accelerators: AcceleratorInfo[]
  recommended_accelerator?: AcceleratorType
  detection_timestamp: string
  detection_duration_ms: number
}

// ============================================================================
// IP Camera Discovery Types
// ============================================================================

export interface DiscoveredCamera {
  ip: string
  name: string | null
  rtsp_url: string | null
  protocol: 'mdns' | 'onvif'
}

export type DiscoveryProtocol = 'mdns' | 'onvif' | 'both'
// ============================================================================
// Real-time Detection Event Types (WebSocket)
// ============================================================================

export interface DetectionBox {
  bbox: [number, number, number, number] // [x1, y1, x2, y2] in pixels
  class_name: string
  class_id: number
  confidence: number
  track_id?: number | null
  /** COCO 17 keypoints [[x, y, conf], ...] — pose task only */
  keypoints?: [number, number, number][]
  /** Polygon vertices [[x, y], ...] — segment task only */
  mask_polygon?: [number, number][]
}

export interface DetectionEvent {
  stream_id: number
  stream_name: string
  timestamp: number
  task_type: 'detect' | 'pose' | 'segment'
  model_name: string
  inference_time_ms: number
  fps: number
  detections: DetectionBox[]
  /** Present only for heartbeat messages */
  heartbeat?: boolean
}
