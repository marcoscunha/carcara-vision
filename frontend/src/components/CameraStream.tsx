import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Stream } from '../types';

interface StreamStats {
    time: string;
    resolution: string;
    fps: number;
    codec: string;
    throughput: string;
}

interface CameraStreamProps {
    stream: Stream;
    protocol?: 'webrtc' | 'mse' | 'hls' | 'mjpeg';
    width?: number;
    autoPlay?: boolean;
    muted?: boolean;
    showStats?: boolean;
    onError?: (error: string) => void;
    onConnected?: () => void;
}

/**
 * CameraStream component for displaying RTSP camera streams via go2rtc.
 *
 * Supports multiple protocols:
 * - webrtc: Low-latency WebRTC stream (default, best for real-time viewing)
 * - mse: Media Source Extensions (good browser compatibility)
 * - hls: HTTP Live Streaming (best compatibility, higher latency)
 * - mjpeg: Motion JPEG (fallback, works everywhere)
 */
const CameraStream: React.FC<CameraStreamProps> = ({
    stream,
    protocol = 'webrtc',
    width = 640,
    autoPlay = true,
    muted = true,
    showStats = true,
    onError,
    onConnected
}) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const pcRef = useRef<RTCPeerConnection | null>(null);
    const [isConnecting, setIsConnecting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentProtocol, setCurrentProtocol] = useState(protocol);

    // Stream statistics state
    const [stats, setStats] = useState<StreamStats>({
        time: '',
        resolution: '-',
        fps: 0,
        codec: '-',
        throughput: '0 KB/s'
    });
    const frameCountRef = useRef(0);
    const lastFrameTimeRef = useRef(Date.now());
    const bytesReceivedRef = useRef(0);
    const lastBytesTimeRef = useRef(Date.now());

    // Update time every second
    useEffect(() => {
        const updateTime = () => {
            const now = new Date();
            setStats(prev => ({
                ...prev,
                time: now.toLocaleTimeString('en-US', { hour12: false })
            }));
        };
        updateTime();
        const interval = setInterval(updateTime, 1000);
        return () => clearInterval(interval);
    }, []);

    // Calculate FPS and throughput from WebRTC stats
    useEffect(() => {
        if (!pcRef.current || currentProtocol !== 'webrtc') return;

        const statsInterval = setInterval(async () => {
            if (!pcRef.current) return;

            try {
                const rtcStats = await pcRef.current.getStats();
                rtcStats.forEach((report) => {
                    if (report.type === 'inbound-rtp' && report.kind === 'video') {
                        // Calculate FPS
                        const currentFrames = report.framesDecoded || 0;
                        const now = Date.now();
                        const timeDiff = (now - lastFrameTimeRef.current) / 1000;

                        if (timeDiff > 0 && frameCountRef.current > 0) {
                            const fps = Math.round((currentFrames - frameCountRef.current) / timeDiff);
                            setStats(prev => ({ ...prev, fps: fps > 0 ? fps : prev.fps }));
                        }
                        frameCountRef.current = currentFrames;
                        lastFrameTimeRef.current = now;

                        // Calculate throughput
                        const currentBytes = report.bytesReceived || 0;
                        const bytesDiff = currentBytes - bytesReceivedRef.current;
                        const throughputTimeDiff = (now - lastBytesTimeRef.current) / 1000;

                        if (throughputTimeDiff > 0) {
                            const bytesPerSec = bytesDiff / throughputTimeDiff;
                            let throughputStr: string;
                            if (bytesPerSec >= 1024 * 1024) {
                                throughputStr = `${(bytesPerSec / (1024 * 1024)).toFixed(2)} MB/s`;
                            } else {
                                throughputStr = `${(bytesPerSec / 1024).toFixed(1)} KB/s`;
                            }
                            setStats(prev => ({ ...prev, throughput: throughputStr }));
                        }
                        bytesReceivedRef.current = currentBytes;
                        lastBytesTimeRef.current = now;
                    }

                    // Get codec info
                    if (report.type === 'codec' && report.mimeType?.includes('video')) {
                        const codecName = report.mimeType.split('/')[1]?.toUpperCase() || '-';
                        setStats(prev => ({ ...prev, codec: codecName }));
                    }
                });
            } catch (e) {
                // Stats not available
            }
        }, 1000);

        return () => clearInterval(statsInterval);
    }, [currentProtocol]);

    // Update resolution when video metadata loads
    useEffect(() => {
        const video = videoRef.current;
        if (!video) return;

        const updateResolution = () => {
            if (video.videoWidth && video.videoHeight) {
                setStats(prev => ({
                    ...prev,
                    resolution: `${video.videoWidth}x${video.videoHeight}`
                }));
            }
        };

        video.addEventListener('loadedmetadata', updateResolution);
        video.addEventListener('resize', updateResolution);

        // Also check periodically in case metadata was already loaded
        if (video.videoWidth && video.videoHeight) {
            updateResolution();
        }

        return () => {
            video.removeEventListener('loadedmetadata', updateResolution);
            video.removeEventListener('resize', updateResolution);
        };
    }, []);

    const retryCountRef = useRef(0);
    const maxRetries = 5;
    const retryDelayMs = 1500;

    // WebRTC connection setup with retry logic
    const connectWebRTC = useCallback(async () => {
        if (!stream.stream_name || !videoRef.current) return;

        setIsConnecting(true);
        setError(null);

        try {
            // Create RTCPeerConnection with minimal ICE config for local network
            const pc = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
                // Optimize for low latency
                bundlePolicy: 'max-bundle',
                rtcpMuxPolicy: 'require',
            });
            pcRef.current = pc;

            // Handle incoming tracks
            pc.ontrack = (event) => {
                if (videoRef.current && event.streams[0]) {
                    videoRef.current.srcObject = event.streams[0];
                    // Start playing immediately
                    videoRef.current.play().catch(() => {});
                    retryCountRef.current = 0; // Reset retry count on success
                    onConnected?.();
                }
            };

            // Handle connection state changes
            pc.onconnectionstatechange = () => {
                if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
                    setError('WebRTC connection failed');
                    onError?.('WebRTC connection failed');
                }
            };

            // Add receive-only transceivers
            pc.addTransceiver('video', { direction: 'recvonly' });
            pc.addTransceiver('audio', { direction: 'recvonly' });

            // Create and set local description
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            // Wait for ICE gathering with very short timeout for minimal latency
            // Local connections don't need long ICE gathering
            await new Promise<void>((resolve) => {
                const timeout = setTimeout(() => {
                    console.log('ICE gathering timeout - proceeding with available candidates');
                    resolve();
                }, 100);

                if (pc.iceGatheringState === 'complete') {
                    clearTimeout(timeout);
                    resolve();
                } else {
                    pc.onicegatheringstatechange = () => {
                        if (pc.iceGatheringState === 'complete') {
                            clearTimeout(timeout);
                            resolve();
                        }
                    };
                }
            });

            // Send offer to go2rtc and get answer - use URL from stream object
            if (!stream.urls?.webrtc) {
                throw new Error('WebRTC URL not available');
            }
            const response = await fetch(stream.urls.webrtc, {
                method: 'POST',
                headers: { 'Content-Type': 'application/sdp' },
                body: pc.localDescription?.sdp
            });

            if (!response.ok) {
                // If 404, the stream might not be ready yet - throw to trigger retry
                if (response.status === 404 && retryCountRef.current < maxRetries) {
                    throw new Error('Stream not ready yet');
                }
                throw new Error(`Failed to connect: ${response.statusText}`);
            }

            const answerSdp = await response.text();
            await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });

            setIsConnecting(false);
            retryCountRef.current = 0; // Reset retry count on success
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : 'Unknown error';

            // Close failed connection
            if (pcRef.current) {
                pcRef.current.close();
                pcRef.current = null;
            }

            // Retry logic for stream not ready
            if (errorMsg === 'Stream not ready yet' && retryCountRef.current < maxRetries) {
                retryCountRef.current++;
                console.log(`Stream not ready, retrying in ${retryDelayMs}ms (attempt ${retryCountRef.current}/${maxRetries})`);
                setTimeout(() => {
                    connectWebRTC();
                }, retryDelayMs);
                return;
            }

            setError(errorMsg);
            onError?.(errorMsg);
            setIsConnecting(false);

            // Fallback to MSE if WebRTC fails after retries
            if (currentProtocol === 'webrtc') {
                console.warn('WebRTC failed, falling back to MSE');
                setCurrentProtocol('mse');
            }
        }
    }, [stream.stream_name, stream.urls, onConnected, onError, currentProtocol]);

    // MSE/HLS connection setup
    const connectMSE = useCallback(() => {
        if (!videoRef.current || !stream.urls) return;

        setIsConnecting(true);
        setError(null);

        const url = currentProtocol === 'hls' ? stream.urls.hls : stream.urls.mse;

        if (currentProtocol === 'hls' && 'Hls' in window) {
            // Use HLS.js if available
            // @ts-ignore
            const hls = new window.Hls();
            hls.loadSource(url);
            hls.attachMedia(videoRef.current);
            hls.on('hlsManifestParsed', () => {
                setIsConnecting(false);
                onConnected?.();
            });
            hls.on('hlsError', (_: any, data: any) => {
                setError(`HLS error: ${data.details}`);
                onError?.(`HLS error: ${data.details}`);
            });
        } else {
            // Direct video source for MSE or native HLS
            videoRef.current.src = url;
            videoRef.current.onloadedmetadata = () => {
                setIsConnecting(false);
                onConnected?.();
            };
            videoRef.current.onerror = () => {
                setError('Failed to load stream');
                onError?.('Failed to load stream');
            };
        }
    }, [stream.urls, currentProtocol, onConnected, onError]);

    // Connect based on protocol
    useEffect(() => {
        if (stream.status !== 'active' || !stream.urls) {
            return;
        }

        if (currentProtocol === 'webrtc') {
            connectWebRTC();
        } else if (currentProtocol === 'mse' || currentProtocol === 'hls') {
            connectMSE();
        } else if (currentProtocol === 'mjpeg' && videoRef.current) {
            // MJPEG is handled via img tag, not video
        }

        return () => {
            // Cleanup WebRTC connection
            if (pcRef.current) {
                pcRef.current.close();
                pcRef.current = null;
            }
            if (videoRef.current) {
                videoRef.current.srcObject = null;
                videoRef.current.src = '';
            }
        };
    }, [stream.status, stream.urls, currentProtocol, connectWebRTC, connectMSE]);

    // Render MJPEG as image
    if (currentProtocol === 'mjpeg' && stream.urls?.mjpeg) {
        return (
            <div className="camera-stream" style={{ width, maxWidth: '100%' }}>
                <div
                    style={{
                        position: 'relative',
                        width: '100%',
                        paddingTop: '56.25%', // 16:9 aspect ratio
                        background: '#18191c',
                        borderRadius: 12,
                        overflow: 'hidden',
                    }}
                >
                    {isConnecting && <div className="loading">Connecting...</div>}
                    {error && <div className="error">{error}</div>}
                    <img
                        src={stream.urls.mjpeg}
                        alt={`Stream ${stream.stream_name}`}
                        style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                            display: 'block',
                            background: '#000',
                        }}
                    />
                    {showStats && (
                        <div style={{
                            position: 'absolute',
                            top: '10px',
                            left: '10px',
                            color: '#00ff00',
                            backgroundColor: 'rgba(0,0,0,0.6)',
                            padding: '8px 12px',
                            borderRadius: '4px',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                            lineHeight: '1.6',
                            pointerEvents: 'none',
                            zIndex: 10,
                        }}>
                            <div>⏱ {stats.time}</div>
                            <div>📐 {stats.resolution}</div>
                            <div>🎬 {stats.fps} fps</div>
                            <div>🎞 MJPEG</div>
                            <div>📶 {stats.throughput}</div>
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // Stats overlay component
    const StatsOverlay = () => showStats ? (
        <div style={{
            position: 'absolute',
            top: '10px',
            left: '10px',
            color: '#00ff00',
            backgroundColor: 'rgba(0,0,0,0.6)',
            padding: '8px 12px',
            borderRadius: '4px',
            fontSize: '12px',
            fontFamily: 'monospace',
            lineHeight: '1.6',
            pointerEvents: 'none',
            zIndex: 10
        }}>
            <div>⏱ {stats.time}</div>
            <div>📐 {stats.resolution}</div>
            <div>🎬 {stats.fps} fps</div>
            <div>🎞 {stats.codec}</div>
            <div>📶 {stats.throughput}</div>
        </div>
    ) : null;

    return (
        <div className="camera-stream" style={{ width, maxWidth: '100%' }}>
            <div
                style={{
                    position: 'relative',
                    width: '100%',
                    paddingTop: '56.25%', // 16:9 aspect ratio
                    background: '#18191c',
                    borderRadius: 12,
                    overflow: 'hidden',
                }}
            >
                {isConnecting && (
                    <div style={{
                        position: 'absolute',
                        top: '50%',
                        left: '50%',
                        transform: 'translate(-50%, -50%)',
                        color: 'white',
                        backgroundColor: 'rgba(0,0,0,0.7)',
                        padding: '10px',
                        borderRadius: '5px',
                        zIndex: 20
                    }}>
                        Connecting...
                    </div>
                )}
                {error && (
                    <div style={{
                        position: 'absolute',
                        top: '50%',
                        left: '50%',
                        transform: 'translate(-50%, -50%)',
                        color: 'red',
                        backgroundColor: 'rgba(0,0,0,0.7)',
                        padding: '10px',
                        borderRadius: '5px',
                        zIndex: 20
                    }}>
                        {error}
                    </div>
                )}
                <video
                    ref={videoRef}
                    autoPlay={autoPlay}
                    muted={muted}
                    playsInline
                    controls
                    disablePictureInPicture
                    // @ts-ignore - disableRemotePlayback is valid but not in types
                    disableRemotePlayback
                    // Low-latency optimizations
                    preload="none"
                    onLoadedData={(e) => {
                        // Seek to live edge to minimize latency
                        const video = e.currentTarget;
                        if (video.buffered.length > 0) {
                            video.currentTime = video.buffered.end(video.buffered.length - 1);
                        }
                        // Set playback rate slightly faster to catch up if behind
                        video.playbackRate = 1.0;
                    }}
                    onWaiting={(e) => {
                        // When buffering, jump to live edge
                        const video = e.currentTarget;
                        if (video.buffered.length > 0) {
                            const liveEdge = video.buffered.end(video.buffered.length - 1);
                            if (liveEdge - video.currentTime > 0.5) {
                                video.currentTime = liveEdge;
                            }
                        }
                    }}
                    onTimeUpdate={(e) => {
                        // Keep close to live edge - if more than 1 second behind, catch up
                        const video = e.currentTarget;
                        if (video.buffered.length > 0) {
                            const liveEdge = video.buffered.end(video.buffered.length - 1);
                            const delay = liveEdge - video.currentTime;
                            if (delay > 1.0) {
                                video.currentTime = liveEdge - 0.1;
                            }
                        }
                    }}
                    style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        display: 'block',
                        background: '#000',
                    }}
                />
                <StatsOverlay />
                {stream.status !== 'active' && (
                    <div style={{
                        position: 'absolute',
                        bottom: '10px',
                        left: '10px',
                        color: 'orange',
                        backgroundColor: 'rgba(0,0,0,0.7)',
                        padding: '5px 10px',
                        borderRadius: '3px',
                        fontSize: '12px',
                        zIndex: 10,
                    }}>
                        Stream: {stream.status}
                    </div>
                )}
            </div>
        </div>
    );
};

export default CameraStream;