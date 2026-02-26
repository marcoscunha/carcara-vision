import React, { useCallback, useEffect, useRef, useState } from 'react'
import { DetectionBox, DetectionEvent, Stream } from '../types'
import { buildDetectionsWsUrl } from '../utils/apiUrl'

// ─── COCO 17-keypoint skeleton ────────────────────────────────────────────────
const COCO_SKELETON: [number, number][] = [
  [0, 1],
  [0, 2],
  [1, 3],
  [2, 4],
  [5, 6],
  [5, 7],
  [7, 9],
  [6, 8],
  [8, 10],
  [5, 11],
  [6, 12],
  [11, 12],
  [11, 13],
  [13, 15],
  [12, 14],
  [14, 16],
]

/** Deterministic class colour from 0-indexed class ID. */
function classColour(classId: number): string {
  const hue = (classId * 37) % 360
  return `hsl(${hue}, 80%, 55%)`
}

// ─── Canvas draw helpers ──────────────────────────────────────────────────────

function drawDetections(ctx: CanvasRenderingContext2D, detections: DetectionBox[], scaleX: number, scaleY: number) {
  for (const det of detections) {
    const [x1, y1, x2, y2] = det.bbox
    const sx1 = x1 * scaleX,
      sy1 = y1 * scaleY
    const sw = (x2 - x1) * scaleX,
      sh = (y2 - y1) * scaleY
    const colour = classColour(det.class_id)

    ctx.strokeStyle = colour
    ctx.lineWidth = 2
    ctx.strokeRect(sx1, sy1, sw, sh)

    const label =
      det.track_id != null
        ? `#${det.track_id} ${det.class_name} ${(det.confidence * 100).toFixed(0)}%`
        : `${det.class_name} ${(det.confidence * 100).toFixed(0)}%`
    drawLabel(ctx, label, sx1, sy1, colour)
  }
}

function drawPose(ctx: CanvasRenderingContext2D, detections: DetectionBox[], scaleX: number, scaleY: number) {
  for (const det of detections) {
    const [x1, y1, x2, y2] = det.bbox
    ctx.strokeStyle = classColour(det.class_id)
    ctx.lineWidth = 2
    ctx.strokeRect(x1 * scaleX, y1 * scaleY, (x2 - x1) * scaleX, (y2 - y1) * scaleY)

    const kpts = det.keypoints
    if (!kpts || kpts.length === 0) continue

    // Draw bones
    ctx.strokeStyle = 'rgba(0,210,255,0.85)'
    ctx.lineWidth = 2
    for (const [a, b] of COCO_SKELETON) {
      if (a >= kpts.length || b >= kpts.length) continue
      const [ax, ay, ac] = kpts[a]
      const [bx, by, bc] = kpts[b]
      if (ac < 0.3 || bc < 0.3) continue
      ctx.beginPath()
      ctx.moveTo(ax * scaleX, ay * scaleY)
      ctx.lineTo(bx * scaleX, by * scaleY)
      ctx.stroke()
    }

    // Draw joints
    for (const [kx, ky, kc] of kpts) {
      if (kc < 0.3) continue
      ctx.beginPath()
      ctx.arc(kx * scaleX, ky * scaleY, 4, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(0,255,100,0.9)'
      ctx.fill()
    }
  }
}

function drawSegmentation(ctx: CanvasRenderingContext2D, detections: DetectionBox[], scaleX: number, scaleY: number) {
  // Draw masks first (semi-transparent fill)
  for (const det of detections) {
    const poly = det.mask_polygon
    if (!poly || poly.length < 3) continue
    const colour = classColour(det.class_id)
    ctx.beginPath()
    ctx.moveTo(poly[0][0] * scaleX, poly[0][1] * scaleY)
    for (let i = 1; i < poly.length; i++) {
      ctx.lineTo(poly[i][0] * scaleX, poly[i][1] * scaleY)
    }
    ctx.closePath()
    ctx.fillStyle = colour.replace('hsl', 'hsla').replace(')', ', 0.35)')
    ctx.fill()
    ctx.strokeStyle = colour
    ctx.lineWidth = 1.5
    ctx.stroke()
  }
  // Draw bounding boxes + labels on top
  drawDetections(ctx, detections, scaleX, scaleY)
}

function drawLabel(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, colour: string) {
  ctx.font = '12px monospace'
  const metrics = ctx.measureText(text)
  const padX = 4,
    padY = 3
  const bh = 16 + padY
  const by = Math.max(y - bh, 0)
  ctx.fillStyle = colour
  ctx.fillRect(x, by, metrics.width + padX * 2, bh)
  ctx.fillStyle = '#fff'
  ctx.fillText(text, x + padX, by + bh - padY)
}

// ─── WebSocket URL helper ────────────────────────────────────────────────────

function buildWsUrl(streamId: number): string {
  return buildDetectionsWsUrl(streamId)
}

// ─── Component ───────────────────────────────────────────────────────────────

interface StreamStats {
  time: string
  resolution: string
  fps: number
  codec: string
  throughput: string
}

interface CameraStreamProps {
  stream: Stream
  protocol?: 'webrtc' | 'mse' | 'hls' | 'mjpeg'
  size?: 'fluid' | 'fixed'
  autoPlay?: boolean
  muted?: boolean
  showStats?: boolean
  /** When true, connect to the annotated WebRTC stream instead of raw */
  showAnnotatedStream?: boolean
  onError?: (error: string) => void
  onConnected?: () => void
}

type StreamProtocol = 'webrtc' | 'mse' | 'hls' | 'mjpeg'

const LOW_LATENCY_PROTOCOL_ORDER: StreamProtocol[] = ['webrtc', 'mse', 'mjpeg', 'hls']

function hasProtocolUrl(protocol: StreamProtocol, stream: Stream, showAnnotatedStream: boolean): boolean {
  if (!stream.urls) return false
  if (protocol === 'webrtc') {
    return Boolean(showAnnotatedStream ? stream.urls.annotated_webrtc : stream.urls.webrtc)
  }
  if (protocol === 'mse') return Boolean(stream.urls.mse)
  if (protocol === 'mjpeg') return Boolean(stream.urls.mjpeg)
  return Boolean(stream.urls.hls)
}

function pickPreferredProtocol(
  stream: Stream,
  showAnnotatedStream: boolean,
  preferred?: StreamProtocol,
): StreamProtocol {
  if (preferred && hasProtocolUrl(preferred, stream, showAnnotatedStream)) {
    return preferred
  }
  for (const candidate of LOW_LATENCY_PROTOCOL_ORDER) {
    if (hasProtocolUrl(candidate, stream, showAnnotatedStream)) {
      return candidate
    }
  }
  return preferred ?? 'webrtc'
}

function nextProtocolAfterFailure(
  failed: StreamProtocol,
  stream: Stream,
  showAnnotatedStream: boolean,
): StreamProtocol | null {
  const failedIndex = LOW_LATENCY_PROTOCOL_ORDER.indexOf(failed)
  if (failedIndex < 0) return null

  for (let i = failedIndex + 1; i < LOW_LATENCY_PROTOCOL_ORDER.length; i++) {
    const candidate = LOW_LATENCY_PROTOCOL_ORDER[i]
    if (hasProtocolUrl(candidate, stream, showAnnotatedStream)) {
      return candidate
    }
  }
  return null
}

/**
 * CameraStream — displays a MediaMTX video stream with an optional AI overlay.
 *
 * The component opens a WebSocket to the backend detection feed and draws
 * bounding boxes / pose skeleton / segmentation masks on a transparent canvas
 * positioned over the video element in real-time (client-side overlay).
 *
 * When ``showAnnotatedStream`` is true the component connects to the
 * server-side annotated RTSP/WebRTC path (boxes already burned into frames).
 */
const CameraStream: React.FC<CameraStreamProps> = ({
  stream,
  protocol = 'webrtc',
  size = 'fluid',
  autoPlay = true,
  muted = true,
  showStats = true,
  showAnnotatedStream = false,
  onError,
  onConnected,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const lastDetectionsRef = useRef<DetectionBox[]>([])
  const animFrameRef = useRef<number>(0)
  const taskTypeRef = useRef<string>('detect')

  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentProtocol, setCurrentProtocol] = useState<StreamProtocol>(() =>
    pickPreferredProtocol(stream, showAnnotatedStream, protocol),
  )
  const [detectionFps, setDetectionFps] = useState(0)
  const protocolLabel = currentProtocol.toUpperCase()

  const detectionEnabled =
    typeof stream.detection_enabled === 'boolean'
      ? stream.detection_enabled
      : Boolean(stream.stream_metadata?.detection_enabled)

  const [stats, setStats] = useState<StreamStats>({
    time: '',
    resolution: '-',
    fps: 0,
    codec: '-',
    throughput: '0 KB/s',
  })
  const frameCountRef = useRef(0)
  const lastFrameTimeRef = useRef(Date.now())
  const bytesReceivedRef = useRef(0)
  const lastBytesTimeRef = useRef(Date.now())

  useEffect(() => {
    setCurrentProtocol(pickPreferredProtocol(stream, showAnnotatedStream, protocol))
  }, [stream, stream.id, stream.urls, showAnnotatedStream, protocol])

  // ── Clock ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    const tick = () => setStats((s) => ({ ...s, time: new Date().toLocaleTimeString('en-US', { hour12: false }) }))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  // ── Canvas resize observer ──────────────────────────────────────────────────
  useEffect(() => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas) return

    const sync = () => {
      const rect = video.getBoundingClientRect()
      canvas.width = rect.width
      canvas.height = rect.height
      canvas.style.width = `${rect.width}px`
      canvas.style.height = `${rect.height}px`
    }
    const ro = new ResizeObserver(sync)
    ro.observe(video)
    sync()
    return () => ro.disconnect()
  }, [])

  // ── Canvas draw loop ────────────────────────────────────────────────────────
  const drawLoop = useCallback(() => {
    const canvas = canvasRef.current
    const video = videoRef.current
    if (!canvas || !video) {
      animFrameRef.current = requestAnimationFrame(drawLoop)
      return
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) {
      animFrameRef.current = requestAnimationFrame(drawLoop)
      return
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    const detections = lastDetectionsRef.current
    if (detections.length > 0 && video.videoWidth > 0) {
      // Scale from model input coords to canvas display coords
      const scaleX = canvas.width / video.videoWidth
      const scaleY = canvas.height / video.videoHeight

      const task = taskTypeRef.current
      if (task === 'pose') {
        drawPose(ctx, detections, scaleX, scaleY)
      } else if (task === 'segment') {
        drawSegmentation(ctx, detections, scaleX, scaleY)
      } else {
        drawDetections(ctx, detections, scaleX, scaleY)
      }
    }

    animFrameRef.current = requestAnimationFrame(drawLoop)
  }, [])

  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(drawLoop)
    return () => cancelAnimationFrame(animFrameRef.current)
  }, [drawLoop])

  // ── WebSocket detection feed ────────────────────────────────────────────────
  useEffect(() => {
    if (!stream.id || showAnnotatedStream || !detectionEnabled || stream.worker_active === false) return // no overlay when disabled/annotated stream or no worker

    const wsUrl = buildWsUrl(stream.id)
    let ws: WebSocket
    let reconnectTimer: ReturnType<typeof setTimeout>
    let stopReconnect = false

    const connect = () => {
      if (stopReconnect) return
      ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onmessage = (ev) => {
        try {
          const event = JSON.parse(ev.data) as DetectionEvent & { error?: string }
          if (event.error?.includes('No active inference worker')) {
            stopReconnect = true
            ws.close()
            return
          }
          if (event.heartbeat) return
          lastDetectionsRef.current = event.detections ?? []
          taskTypeRef.current = event.task_type ?? 'detect'
          setDetectionFps(event.fps)
        } catch {
          /* ignore parse errors */
        }
      }

      ws.onclose = () => {
        if (stopReconnect) return
        reconnectTimer = setTimeout(connect, 3000)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()
    return () => {
      clearTimeout(reconnectTimer)
      if (wsRef.current) wsRef.current.close()
      wsRef.current = null
      lastDetectionsRef.current = []
    }
  }, [stream.id, stream.worker_active, showAnnotatedStream, detectionEnabled])

  // ── WebRTC stats ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!pcRef.current || currentProtocol !== 'webrtc') return
    const id = setInterval(async () => {
      if (!pcRef.current) return
      try {
        const rtcStats = await pcRef.current.getStats()
        rtcStats.forEach((report) => {
          if (report.type === 'inbound-rtp' && report.kind === 'video') {
            const now = Date.now()
            const currentFrames = report.framesDecoded || 0
            const diff = (now - lastFrameTimeRef.current) / 1000
            if (diff > 0 && frameCountRef.current > 0) {
              const fps = Math.round((currentFrames - frameCountRef.current) / diff)
              setStats((s) => ({ ...s, fps: fps > 0 ? fps : s.fps }))
            }
            frameCountRef.current = currentFrames
            lastFrameTimeRef.current = now

            const currentBytes = report.bytesReceived || 0
            const bytesDiff = currentBytes - bytesReceivedRef.current
            const timeDiff = (now - lastBytesTimeRef.current) / 1000
            if (timeDiff > 0) {
              const bps = bytesDiff / timeDiff
              const str = bps >= 1048576 ? `${(bps / 1048576).toFixed(2)} MB/s` : `${(bps / 1024).toFixed(1)} KB/s`
              setStats((s) => ({ ...s, throughput: str }))
            }
            bytesReceivedRef.current = currentBytes
            lastBytesTimeRef.current = now
          }
          if (report.type === 'codec' && report.mimeType?.includes('video')) {
            const codec = report.mimeType.split('/')[1]?.toUpperCase() || '-'
            setStats((s) => ({ ...s, codec }))
          }
        })
      } catch {
        /* stats not available yet */
      }
    }, 1000)
    return () => clearInterval(id)
  }, [currentProtocol])

  // ── Resolution update ───────────────────────────────────────────────────────
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const update = () => {
      if (video.videoWidth && video.videoHeight)
        setStats((s) => ({ ...s, resolution: `${video.videoWidth}x${video.videoHeight}` }))
    }
    video.addEventListener('loadedmetadata', update)
    video.addEventListener('resize', update)
    if (video.videoWidth) update()
    return () => {
      video.removeEventListener('loadedmetadata', update)
      video.removeEventListener('resize', update)
    }
  }, [])

  // ── WebRTC connection ───────────────────────────────────────────────────────
  const retryCountRef = useRef(0)
  const maxRetries = 5
  const retryDelayMs = 1500

  const connectWebRTC = useCallback(async () => {
    if (!stream.stream_name || !videoRef.current) return
    setIsConnecting(true)
    setError(null)

    try {
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
        bundlePolicy: 'max-bundle',
        rtcpMuxPolicy: 'require',
      })
      pcRef.current = pc

      pc.ontrack = (event) => {
        if (videoRef.current && event.streams[0]) {
          videoRef.current.srcObject = event.streams[0]
          videoRef.current.play().catch(() => {})
          retryCountRef.current = 0
          onConnected?.()
        }
      }
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
          setError('WebRTC connection failed')
          onError?.('WebRTC connection failed')
        }
      }

      pc.addTransceiver('video', { direction: 'recvonly' })
      pc.addTransceiver('audio', { direction: 'recvonly' })

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      await new Promise<void>((resolve) => {
        const timeout = setTimeout(resolve, 100)
        if (pc.iceGatheringState === 'complete') {
          clearTimeout(timeout)
          resolve()
          return
        }
        pc.onicegatheringstatechange = () => {
          if (pc.iceGatheringState === 'complete') {
            clearTimeout(timeout)
            resolve()
          }
        }
      })

      // Use annotated WebRTC URL when showAnnotatedStream is true
      const whepUrl = showAnnotatedStream ? stream.urls?.annotated_webrtc : stream.urls?.webrtc

      if (!whepUrl) throw new Error('WebRTC URL not available')

      const response = await fetch(whepUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/sdp' },
        body: pc.localDescription?.sdp,
      })
      if (!response.ok) {
        if (response.status === 404 && retryCountRef.current < maxRetries) throw new Error('Stream not ready yet')
        throw new Error(`Failed to connect: ${response.statusText}`)
      }
      const answerSdp = await response.text()
      await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp })
      setIsConnecting(false)
      retryCountRef.current = 0
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      if (pcRef.current) {
        pcRef.current.close()
        pcRef.current = null
      }
      if (msg === 'Stream not ready yet' && retryCountRef.current < maxRetries) {
        retryCountRef.current++
        setTimeout(connectWebRTC, retryDelayMs)
        return
      }
      setError(msg)
      onError?.(msg)
      setIsConnecting(false)
      if (currentProtocol === 'webrtc') {
        const nextProtocol = nextProtocolAfterFailure('webrtc', stream, showAnnotatedStream)
        if (nextProtocol) setCurrentProtocol(nextProtocol)
      }
    }
  }, [stream, showAnnotatedStream, onConnected, onError, currentProtocol])

  // ── MSE / HLS connection ────────────────────────────────────────────────────
  const connectMSE = useCallback(() => {
    if (!videoRef.current || !stream.urls) return
    setIsConnecting(true)
    setError(null)
    const url = currentProtocol === 'hls' ? stream.urls.hls : stream.urls.mse
    if (currentProtocol === 'hls' && 'Hls' in window) {
      // @ts-ignore
      const hls = new window.Hls()
      hls.loadSource(url)
      hls.attachMedia(videoRef.current)
      hls.on('hlsManifestParsed', () => {
        setIsConnecting(false)
        onConnected?.()
      })
      hls.on('hlsError', (_: any, data: any) => {
        setError(`HLS error: ${data.details}`)
        onError?.(`HLS error: ${data.details}`)
        const nextProtocol = nextProtocolAfterFailure('hls', stream, showAnnotatedStream)
        if (nextProtocol) setCurrentProtocol(nextProtocol)
      })
    } else {
      videoRef.current.src = url
      videoRef.current.onloadedmetadata = () => {
        setIsConnecting(false)
        onConnected?.()
      }
      videoRef.current.onerror = () => {
        setError('Failed to load stream')
        onError?.('Failed to load stream')
        const nextProtocol = nextProtocolAfterFailure(currentProtocol, stream, showAnnotatedStream)
        if (nextProtocol) setCurrentProtocol(nextProtocol)
      }
    }
  }, [stream, currentProtocol, onConnected, onError, showAnnotatedStream])

  // ── Protocol switch ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (stream.status !== 'active' || !stream.urls) return
    if (currentProtocol === 'webrtc') connectWebRTC()
    else if (currentProtocol === 'mse' || currentProtocol === 'hls') connectMSE()

    return () => {
      if (pcRef.current) {
        pcRef.current.close()
        pcRef.current = null
      }
      if (videoRef.current) {
        videoRef.current.srcObject = null
        videoRef.current.src = ''
      }
    }
  }, [stream.status, stream.urls, currentProtocol, connectWebRTC, connectMSE, showAnnotatedStream])

  // ── MJPEG fallback ──────────────────────────────────────────────────────────
  if (currentProtocol === 'mjpeg' && stream.urls?.mjpeg) {
    return (
      <div className={`camera-stream ${size === 'fixed' ? 'camera-stream--fixed' : ''}`.trim()}>
        <div className="camera-stream__frame">
          <div className="camera-stream__protocol-badge">{protocolLabel}</div>
          {isConnecting && <div className="camera-stream__notice camera-stream__notice--connecting">Connecting...</div>}
          {error && <div className="camera-stream__notice camera-stream__notice--error">{error}</div>}
          <img src={stream.urls.mjpeg} alt={`Stream ${stream.stream_name}`} className="camera-stream__image" />
          {showStats && (
            <div className="camera-stream__stats">
              <div>⏱ {stats.time}</div>
              <div>📐 {stats.resolution}</div>
              <div>🎬 {stats.fps} fps</div>
              <div>🎞 MJPEG</div>
              <div>📶 {stats.throughput}</div>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={`camera-stream ${size === 'fixed' ? 'camera-stream--fixed' : ''}`.trim()}>
      <div className="camera-stream__frame" style={{ position: 'relative' }}>
        <div className="camera-stream__protocol-badge">{protocolLabel}</div>
        {isConnecting && <div className="camera-stream__notice camera-stream__notice--connecting">Connecting...</div>}
        {error && <div className="camera-stream__notice camera-stream__notice--error">{error}</div>}

        <video
          ref={videoRef}
          autoPlay={autoPlay}
          muted={muted}
          playsInline
          controls
          disablePictureInPicture
          // @ts-ignore
          disableRemotePlayback
          preload="none"
          onLoadedData={(e) => {
            const video = e.currentTarget
            if (video.buffered.length > 0) video.currentTime = video.buffered.end(video.buffered.length - 1)
          }}
          onWaiting={(e) => {
            const video = e.currentTarget
            if (video.buffered.length > 0) {
              const liveEdge = video.buffered.end(video.buffered.length - 1)
              if (liveEdge - video.currentTime > 0.5) video.currentTime = liveEdge
            }
          }}
          onTimeUpdate={(e) => {
            const video = e.currentTarget
            if (video.buffered.length > 0) {
              const liveEdge = video.buffered.end(video.buffered.length - 1)
              if (liveEdge - video.currentTime > 1.0) video.currentTime = liveEdge - 0.1
            }
          }}
          className="camera-stream__video"
        />

        {/* Detection overlay canvas — only when NOT using server-side annotated stream */}
        {!showAnnotatedStream && (
          <canvas
            ref={canvasRef}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              pointerEvents: 'none',
            }}
          />
        )}

        {/* Stats overlay */}
        {showStats && (
          <div className="camera-stream__stats">
            <div>⏱ {stats.time}</div>
            <div>📐 {stats.resolution}</div>
            <div>🎬 {stats.fps} fps</div>
            <div>🎞 {stats.codec}</div>
            <div>📶 {stats.throughput}</div>
            {detectionFps > 0 && <div>🤖 AI {detectionFps.toFixed(1)} fps</div>}
            {showAnnotatedStream && <div>🖌 Server overlay</div>}
          </div>
        )}

        {stream.status !== 'active' && <div className="camera-stream__status">Stream: {stream.status}</div>}
      </div>
    </div>
  )
}

export default CameraStream
