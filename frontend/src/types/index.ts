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