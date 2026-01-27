export interface Camera {
  id: number;
  name: string;
  rtsp_url: string;
  is_active: boolean;
  device_id: number;
  resolution: [number, number];
  fps: number;
  is_available: boolean;
  camera_type: string;
  created_at: string;
  updated_at: string;
}

export interface StreamURLs {
  rtsp: string;
  webrtc: string;
  hls: string;
  mse: string;
  mjpeg: string;
  ws: string;
}

export interface Stream {
  id: number;
  camera_id: number;
  stream_name: string;
  status: string;
  current_frame: number;
  urls: StreamURLs | null;
  stream_metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface StreamCreate {
  camera_id: number;
  width?: number;
  height?: number;
  codec?: string;
  stream_metadata?: Record<string, any>;
}

export interface Detection {
  id: number;
  camera_id: number;
  stream_id: number;
  frame_number: number;
  timestamp: string;
  model_name: string;
  confidence: number;
  class_name: string;
  bbox: number[];
  metadata: Record<string, any>;
}

export interface Alarm {
  id: number;
  name: string;
  camera_id: number;
  class_name: string;
  confidence_threshold: number;
  region_of_interest: number[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Model {
  name: string;
  description: string;
  is_available: boolean;
  confidence_threshold: number;
}

export interface RegionOfInterest {
  id: number;
  name: string;
  camera_id: number;
  points: number[][];
  created_at: string;
  updated_at: string;
}

// ============================================================================
// Hardware Detection Types
// ============================================================================

export type CPUArchitecture =
  | 'x86_64'
  | 'x86'
  | 'arm64'
  | 'armv7'
  | 'armv8'
  | 'unknown';

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
  | 'unknown';

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
  | 'cpu';

export type AcceleratorStatus =
  | 'available'
  | 'unavailable'
  | 'driver_missing'
  | 'not_detected'
  | 'error';

export interface CPUInfo {
  architecture: CPUArchitecture;
  model_name: string;
  vendor: string;
  cores: number;
  threads: number;
  max_frequency_mhz?: number;
  features: string[];
}

export interface MemoryInfo {
  total_gb: number;
  available_gb: number;
  used_percent: number;
}

export interface PlatformInfo {
  vendor: PlatformVendor;
  board_name: string;
  board_model?: string;
  serial_number?: string;
  os_name: string;
  os_version: string;
  kernel_version: string;
}

export interface AcceleratorInfo {
  type: AcceleratorType;
  name: string;
  status: AcceleratorStatus;
  driver_version?: string;
  firmware_version?: string;
  memory_mb?: number;
  compute_capability?: string;
  device_path?: string;
  pcie_address?: string;
  details: Record<string, unknown>;
}

export interface HardwareDetectionResult {
  cpu: CPUInfo;
  memory: MemoryInfo;
  platform: PlatformInfo;
  accelerators: AcceleratorInfo[];
  recommended_accelerator?: AcceleratorType;
  detection_timestamp: string;
  detection_duration_ms: number;
}