import axios from 'axios';
import { Camera, Stream, StreamCreate, Detection, Alarm, Model, RegionOfInterest, StreamURLs } from '../types';

const API_URL = 'http://localhost:8000/api/v1';
export const GO2RTC_URL = 'http://localhost:1984';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface CameraInfo {
  device_id: number;
  physical_address?: string;
  usb_id?: string;
  name: string;
  friendly_name?: string;
  resolution: [number, number];
  fps: number;
  is_available: boolean;
  supported_resolutions: [number, number][];
}

export interface ApiResponse<T> {
  data: T;
}

// Camera endpoints
export const cameraApi = {
  getAll: async () => {
    const response = await api.get<ApiResponse<Camera[]>>('/cameras/');
    return response.data;
  },
  get: (id: number) => api.get<Camera>(`/cameras/${id}`),
  create: (camera: Partial<Camera>) => api.post<Camera>('/cameras/', camera),
  update: (id: number, camera: Partial<Camera>) => api.put<Camera>(`/cameras/${id}`, camera),
  delete: (id: number) => api.delete(`/cameras/${id}`),
  scan: () => api.get<CameraInfo[]>('/cameras/scan'),
};

// Stream endpoints
export const streamApi = {
  getAll: async (status?: string) => {
    const params = status ? { status } : {};
    const response = await api.get<ApiResponse<Stream[]>>('/streams/', { params });
    return response.data;
  },
  getById: (id: number) => api.get<Stream>(`/streams/${id}`),
  getUrls: (id: number) => api.get<StreamURLs>(`/streams/${id}/urls`),
  create: (data: StreamCreate) => api.post<Stream>('/streams/', data),
  update: (id: number, data: Partial<Stream>) =>
    api.put<Stream>(`/streams/${id}`, data),
  delete: (id: number) => api.delete(`/streams/${id}`),
  restart: (id: number) => api.post<Stream>(`/streams/${id}/restart`),
  checkHealth: () => api.get('/streams/health/go2rtc'),
};

// Detection endpoints
export const detectionApi = {
  getAll: async (params?: { camera_id?: number; stream_id?: number }) => {
    const response = await api.get<ApiResponse<Detection[]>>('/detections', { params });
    return response.data;
  },
  getById: (id: number) => api.get<Detection>(`/detections/${id}`),
  create: (data: Omit<Detection, 'id' | 'timestamp'>) =>
    api.post<Detection>('/detections', data),
  delete: (id: number) => api.delete(`/detections/${id}`),
};

// Alarm endpoints
export const alarmApi = {
  getAll: async () => {
    const response = await api.get<ApiResponse<Alarm[]>>('/alarms');
    return response.data;
  },
  getById: (id: number) => api.get<Alarm>(`/alarms/${id}`),
  create: (data: Omit<Alarm, 'id' | 'created_at' | 'updated_at'>) =>
    api.post<Alarm>('/alarms', data),
  update: (id: number, data: Partial<Alarm>) =>
    api.put<Alarm>(`/alarms/${id}`, data),
  delete: (id: number) => api.delete(`/alarms/${id}`),
};

// Model endpoints
export const modelApi = {
  getAll: async () => {
    const response = await api.get<ApiResponse<Model[]>>('/models');
    return response.data;
  },
  getById: (name: string) => api.get<Model>(`/models/${name}`),
  update: (name: string, data: Partial<Model>) =>
    api.put<Model>(`/models/${name}`, data),
};

// Region of Interest endpoints
export const roiApi = {
  getAll: async (camera_id: number) => {
    const response = await api.get<ApiResponse<RegionOfInterest[]>>('/roi', { params: { camera_id } });
    return response.data;
  },
  getById: (id: number) => api.get<RegionOfInterest>(`/roi/${id}`),
  create: (data: Omit<RegionOfInterest, 'id' | 'created_at' | 'updated_at'>) =>
    api.post<RegionOfInterest>('/roi', data),
  update: (id: number, data: Partial<RegionOfInterest>) =>
    api.put<RegionOfInterest>(`/roi/${id}`, data),
  delete: (id: number) => api.delete(`/roi/${id}`),
};