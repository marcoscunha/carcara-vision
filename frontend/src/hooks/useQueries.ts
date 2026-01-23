import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  cameraApi,
  streamApi,
  detectionApi,
  alarmApi,
  modelApi,
  roiApi,
} from '../services/api';
import { Camera, Stream, StreamCreate, Detection, Alarm, Model, RegionOfInterest } from '../types';

// Query Keys - centralized for consistency
export const queryKeys = {
  cameras: {
    all: ['cameras'] as const,
    detail: (id: number) => ['cameras', id] as const,
    scan: ['cameras', 'scan'] as const,
  },
  streams: {
    all: ['streams'] as const,
    byStatus: (status?: string) => ['streams', { status }] as const,
    detail: (id: number) => ['streams', id] as const,
    urls: (id: number) => ['streams', id, 'urls'] as const,
    health: ['streams', 'health'] as const,
  },
  detections: {
    all: ['detections'] as const,
    filtered: (params?: { camera_id?: number; stream_id?: number }) =>
      ['detections', params] as const,
    detail: (id: number) => ['detections', id] as const,
  },
  alarms: {
    all: ['alarms'] as const,
    detail: (id: number) => ['alarms', id] as const,
  },
  models: {
    all: ['models'] as const,
    detail: (name: string) => ['models', name] as const,
  },
  roi: {
    byCamera: (cameraId: number) => ['roi', cameraId] as const,
    detail: (id: number) => ['roi', 'detail', id] as const,
  },
};

// ============ CAMERA HOOKS ============

export const useCameras = () => {
  return useQuery({
    queryKey: queryKeys.cameras.all,
    queryFn: cameraApi.getAll,
  });
};

export const useCamera = (id: number) => {
  return useQuery({
    queryKey: queryKeys.cameras.detail(id),
    queryFn: () => cameraApi.get(id).then(res => res.data),
    enabled: !!id,
  });
};

export const useScanCameras = () => {
  return useQuery({
    queryKey: queryKeys.cameras.scan,
    queryFn: () => cameraApi.scan().then(res => res.data),
    enabled: false, // Manual trigger only
  });
};

export const useCreateCamera = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (camera: Partial<Camera>) => cameraApi.create(camera),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
    },
  });
};

export const useUpdateCamera = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Camera> }) =>
      cameraApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.cameras.detail(variables.id) });
    },
  });
};

export const useDeleteCamera = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => cameraApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
      // Also invalidate streams since they are cascade deleted with camera
      queryClient.invalidateQueries({ queryKey: queryKeys.streams.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.detections.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.alarms.all });
    },
  });
};

// ============ STREAM HOOKS ============

export const useStreams = (status?: string) => {
  return useQuery({
    queryKey: queryKeys.streams.byStatus(status),
    queryFn: () => streamApi.getAll(status),
  });
};

export const useStream = (id: number) => {
  return useQuery({
    queryKey: queryKeys.streams.detail(id),
    queryFn: () => streamApi.getById(id).then(res => res.data),
    enabled: !!id,
  });
};

export const useStreamUrls = (id: number) => {
  return useQuery({
    queryKey: queryKeys.streams.urls(id),
    queryFn: () => streamApi.getUrls(id).then(res => res.data),
    enabled: !!id,
  });
};

export const useStreamHealth = () => {
  return useQuery({
    queryKey: queryKeys.streams.health,
    queryFn: () => streamApi.checkHealth(),
    refetchInterval: 30000, // Check health every 30 seconds
  });
};

export const useCreateStream = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: StreamCreate) => streamApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.streams.all });
    },
  });
};

export const useUpdateStream = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Stream> }) =>
      streamApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.streams.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.streams.detail(variables.id) });
    },
  });
};

export const useDeleteStream = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => streamApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.streams.all });
    },
  });
};

export const useRestartStream = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => streamApi.restart(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.streams.detail(id) });
    },
  });
};

// ============ DETECTION HOOKS ============

export const useDetections = (params?: { camera_id?: number; stream_id?: number }) => {
  return useQuery({
    queryKey: queryKeys.detections.filtered(params),
    queryFn: () => detectionApi.getAll(params),
  });
};

export const useDetection = (id: number) => {
  return useQuery({
    queryKey: queryKeys.detections.detail(id),
    queryFn: () => detectionApi.getById(id).then(res => res.data),
    enabled: !!id,
  });
};

export const useCreateDetection = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Omit<Detection, 'id' | 'timestamp'>) => detectionApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.detections.all });
    },
  });
};

export const useDeleteDetection = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => detectionApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.detections.all });
    },
  });
};

// ============ ALARM HOOKS ============

export const useAlarms = () => {
  return useQuery({
    queryKey: queryKeys.alarms.all,
    queryFn: alarmApi.getAll,
  });
};

export const useAlarm = (id: number) => {
  return useQuery({
    queryKey: queryKeys.alarms.detail(id),
    queryFn: () => alarmApi.getById(id).then(res => res.data),
    enabled: !!id,
  });
};

export const useCreateAlarm = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Omit<Alarm, 'id' | 'created_at' | 'updated_at'>) =>
      alarmApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.alarms.all });
    },
  });
};

export const useUpdateAlarm = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Alarm> }) =>
      alarmApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.alarms.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.alarms.detail(variables.id) });
    },
  });
};

export const useDeleteAlarm = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => alarmApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.alarms.all });
    },
  });
};

// ============ MODEL HOOKS ============

export const useModels = () => {
  return useQuery({
    queryKey: queryKeys.models.all,
    queryFn: modelApi.getAll,
  });
};

export const useModel = (name: string) => {
  return useQuery({
    queryKey: queryKeys.models.detail(name),
    queryFn: () => modelApi.getById(name).then(res => res.data),
    enabled: !!name,
  });
};

export const useUpdateModel = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: Partial<Model> }) =>
      modelApi.update(name, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.models.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.models.detail(variables.name) });
    },
  });
};

// ============ ROI HOOKS ============

export const useROIs = (cameraId: number) => {
  return useQuery({
    queryKey: queryKeys.roi.byCamera(cameraId),
    queryFn: () => roiApi.getAll(cameraId),
    enabled: !!cameraId,
  });
};

export const useROI = (id: number) => {
  return useQuery({
    queryKey: queryKeys.roi.detail(id),
    queryFn: () => roiApi.getById(id).then(res => res.data),
    enabled: !!id,
  });
};

export const useCreateROI = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Omit<RegionOfInterest, 'id' | 'created_at' | 'updated_at'>) =>
      roiApi.create(data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.roi.byCamera(variables.camera_id) });
    },
  });
};

export const useUpdateROI = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<RegionOfInterest> }) =>
      roiApi.update(id, data),
    onSuccess: () => {
      // Invalidate all ROI queries since we may not know the camera_id
      queryClient.invalidateQueries({ queryKey: ['roi'] });
    },
  });
};

export const useDeleteROI = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => roiApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roi'] });
    },
  });
};
