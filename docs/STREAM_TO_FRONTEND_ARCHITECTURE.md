# 📹 End-to-End Streaming + AI Architecture (Camera → Model → Frontend)

This document reviews the current implementation in this repository and maps the main package usage from camera acquisition to frontend visualization, including codecs and transport protocols.

## 1) Architecture blocks (media + AI path)

```text
[CAMERA SOURCES]
  +--------------------------------+       +--------------------------------+
  | USB / Local Camera             |       | IP Camera                      |
  | V4L2 device                    |       | RTSP URL                       |
  +---------------+----------------+       +---------------+----------------+
                  |                                        |
                  | V4L2                                   | RTSP (typically H.264)
                  v                                        v
[GSTREAMER PIPELINE MANAGER]
  +-------------------------------+    +-------------------------------------+
  | V4L2 ingest                   |    | RTSP ingest                         |
  | v4l2src + videoconvert        |    | rtspsrc + rtph264depay + h264parse |
  +---------------+---------------+    +------------------+------------------+
                  |                                   \
                  v                                    \
  +---------------------------------------------+       \
  | Encoder                                      |        \
  | x264enc or x265enc                           |         \
  +----------------------+-----------------------+          \
                         |                                   \
                         v                                    v
  +---------------------------------------------------------------+
  | Publisher: rtspclientsink -> MediaMTX raw path               |
  | rtsp://.../stream_name                                       |
  +------------------------------+--------------------------------+
                                 |
                                 | RTSP read
                                 v
[AI PROCESSING]
  +----------------------------------------------+
  | InferenceWorker (OpenCV VideoCapture RTSP)   |
  +----------------------+-----------------------+
                         v
  +----------------------------------------------+
  | ObjectDetectionService + InferenceEngineFactory |
  +----------------------+-----------------------+
                         v
  +----------------------------------------------+
  | YOLO engine (track / detect / pose / segment) |
  +-----------+-------------------+---------------+
              |                   |
              | WS JSON           | annotated frame
              v                   v
  +---------------------------+   +-------------------------------------------+
  | DetectionEvent broadcast  |   | FrameAnnotator + AnnotatedStreamWriter    |
  | /api/v1/ws/streams/...    |   | FFmpeg libx264 -> RTSP annotated_stream   |
  +-------------+-------------+   +-------------------+-----------------------+
                |                                     |
                v                                     v
[FRONTEND]                                        [MEDIAMTX DISTRIBUTION]
  +-------------------------------------------+     +--------------------------------------+
  | Optional client overlay (canvas + WS)     |     | Protocol fanout                      |
  | in CameraStream.tsx                        |     | WHEP/WebRTC, HLS, RTSP, MSE          |
  +-------------------+-----------------------+     +----------------+---------------------+
                      \                                         /
                       \                                       /
                        v                                     v
                  +-----------------------------------------------+
                  | CameraStream.tsx player                       |
                  | WebRTC preferred, MSE/HLS fallback            |
                  | Optional server overlay via annotated_webrtc  |
                  +-----------------------------------------------+

[BACKEND CONTROL PLANE]
  FastAPI API endpoints (/cameras, /streams, /inference-runtime)
      -> GStreamerService (HTTP control to pipeline manager :8085 /api/streams)
      -> InferenceWorkerManager (start/stop per-stream workers)
```

---

## 2) Protocol and codec transitions (explicit)

```text
[USB camera]
  Raw frames
    --(V4L2)--> [GStreamer v4l2src]
    --(video/x-raw)--> [x264enc or x265enc]
    --(RTP over RTSP publish)--> [MediaMTX raw path]

[IP camera stream]
  RTSP input (current pipeline expects H.264 depayload)
    --(RTSP)--> [rtspsrc + rtph264depay + h264parse]
    --(RTSP publish)--> [MediaMTX raw path]

[MediaMTX raw path]
    --(RTSP)--> [InferenceWorker OpenCV capture]
    --(NumPy BGR frame)--> [YOLO inference]
    --(annotated BGR frame)--> [FFmpeg stdin rawvideo bgr24]
    --(libx264 + yuv420p)--> [RTSP publish annotated_stream]
    --(RTSP / WebRTC(H.264) / HLS(MPEG-TS))--> [Frontend player]

[YOLO inference]
    --(JSON over WebSocket)--> [Frontend detection overlay]
```

### Current codec notes from implementation

- GStreamer manager (`gstreamer/pipeline_manager.py`) encodes local/test sources using `x264enc` (default) or `x265enc`.
- RTSP source ingest in the manager is currently wired as `rtspsrc ! rtph264depay ! h264parse` (expects H.264 payload on source side).
- Annotated stream writer (`backend/src/services/annotated_stream_writer.py`) always encodes with `libx264`, `yuv420p`, RTSP over TCP.
- MediaMTX is configured to expose RTSP (`8554`), WebRTC/WHEP (`8889`), HLS (`8888`) and API (`9997`) in `mediamtx/mediamtx.yml`.

---

## 3) Main package usage by stage

### A. Acquisition + stream registration

- `backend/src/api/endpoints/cameras.py`: camera CRUD and local camera scan.
- `backend/src/services/camera_service.py`: V4L2 discovery, persistent `/dev/v4l/by-id` handling.
- `backend/src/api/endpoints/streams.py`: stream creation/update lifecycle and metadata.
- `backend/src/services/gstreamer.py`: backend adapter to pipeline manager + MediaMTX URLs.

### B. Media pipeline + distribution

- `gstreamer/pipeline_manager.py`: builds and runs per-stream GStreamer pipelines; publishes to MediaMTX.
- `mediamtx/mediamtx.yml`: protocol fan-out and media server behavior.

### C. Inference pipeline

- `backend/src/services/inference_worker_manager.py`: one worker per active stream with detection enabled.
- `backend/src/services/inference_worker.py`: RTSP frame pull, inference loop, annotation, WS event broadcast.
- `backend/src/services/object_detection.py`: model service facade, hardware selection, stats.
- `backend/src/ml/factory.py`: engine/backend construction (`YOLO`, `ONNX`, `TensorRT`, `VLM`).
- `backend/src/ml/engines/yolo.py`: detect/track/pose/segment execution.
- `backend/src/ml/registry.py`: model catalog + task types (`detect`, `pose`, `segment`).
- `backend/src/services/annotated_stream_writer.py`: FFmpeg-based annotated RTSP publisher.

### D. Frontend rendering + real-time events

- `frontend/src/components/CameraStream.tsx`: media playback (WebRTC preferred, then MSE/HLS/MJPEG), optional overlay.
- `frontend/src/utils/apiUrl.ts`: detection WebSocket URL generation.
- `backend/src/api/endpoints/ws_detections.py`: WebSocket detection event stream.
- `frontend/src/types/index.ts`: stream URL and detection event contracts.

---

## 4) Observed end-to-end runtime sequence

1. Frontend calls backend `/api/v1/streams/` to create stream.
2. Backend creates DB stream record, calls GStreamer manager (`PUT /api/streams`) via `GStreamerService`.
3. GStreamer starts pipeline and publishes RTSP to MediaMTX path `<stream_name>`.
4. Backend starts `InferenceWorker` for that stream if detection is enabled.
5. Worker reads raw stream from MediaMTX RTSP, runs YOLO inference, emits detection JSON via WS.
6. Worker publishes annotated stream to MediaMTX `annotated_<stream_name>`.
7. Frontend `CameraStream` connects to raw or annotated media URL (WHEP/WebRTC preferred) and optionally overlays WS detections.

---

## 5) Quick architecture review (what is strong / what to watch)

### Strengths

- Clean separation between control plane (FastAPI) and media plane (GStreamer + MediaMTX).
- Per-stream AI workers isolate inference workloads and simplify stream-level scaling.
- Dual visualization model is flexible: client overlay (WS + canvas) or server-burned overlay (annotated stream).

### Watch points

- RTSP ingest path in pipeline manager is H.264-specific; non-H.264 camera streams may require pipeline branch extension.
- `mjpeg` URL currently maps to HLS path in `backend/src/services/gstreamer.py` (naming may be misleading to clients).
- End-to-end latency can vary with protocol fallback (WebRTC < MSE/HLS in most deployments).

## 6) Two-flow strategy and sync recommendation

Current product behavior intentionally supports two visualization flows:

1. Client overlay flow (raw video + WebSocket detections + canvas draw in frontend)
2. Backend-centered sync flow (server-annotated video path `annotated_<stream_name>`)

### Recommendation for video/prediction synchronization

To minimize visual drift between boxes and frames, prefer the backend-centered sync flow for operator views:

- Detection and annotation happen in the same backend worker loop.
- Annotated frames are dispatched as a single media stream.
- Frontend consumes that stream directly, so timing is governed by one pipeline.

This reduces mismatches caused by independent browser scheduling of video decode and WebSocket events.

### Feature flag and runtime control

Sync flow can be controlled at two levels:

- Global default via backend environment variable:
  - `VIDEO_PREDICTION_SYNC_ENABLED=true|false`
- Per-stream override via stream metadata/API field:
  - `sync_video_predictions`

Behavior:

- When `sync_video_predictions=true`, frontend uses the annotated stream path (`showAnnotatedStream=true`) and does not apply client-side WS overlay.
- When `sync_video_predictions=false`, frontend uses raw stream + client-side overlay (legacy flow).

This keeps rollout safe: you can enable sync only for selected streams, then promote it to default globally.
