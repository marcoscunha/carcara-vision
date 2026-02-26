"""
WebSocket endpoint for real-time detection events.

Clients connect to::

    WS /api/v1/ws/streams/{stream_id}/detections

and receive a continuous stream of JSON detection events emitted by the
``InferenceWorker`` for that stream.

Message format (JSON)::

    {
        "stream_id":        int,
        "stream_name":      str,
        "timestamp":        float,       # Unix epoch seconds
        "task_type":        str,         # detect | pose | segment
        "model_name":       str,
        "inference_time_ms": float,
        "fps":              float,
        "detections": [
            {
                "bbox":         [x1, y1, x2, y2],
                "class_name":   str,
                "class_id":     int,
                "confidence":   float,
                "track_id":     int | null,       # detect only
                "keypoints":    [[x, y, c], ...], # pose only (17 joints)
                "mask_polygon": [[x, y], ...],    # segment only
            },
            ...
        ]
    }

If no worker is active for the requested stream the server sends::

    {"error": "No active inference worker for stream {id}"}

and closes the connection.

The WS router is mounted under the ``/api/v1/ws`` prefix in main.py.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi import WebSocket
from fastapi import WebSocketDisconnect

from ...services.inference_worker_manager import inference_worker_manager

logger = logging.getLogger(__name__)

router = APIRouter()

_SUBSCRIBER_QUEUE_SIZE = 60  # buffer up to 60 frames before dropping


@router.websocket("/streams/{stream_id}/detections")
async def ws_stream_detections(stream_id: int, websocket: WebSocket):
    """
    Stream real-time detection events to a WebSocket client.

    The connection stays alive as long as the inference worker runs.
    Clients should handle disconnection and reconnect as needed.
    """
    await websocket.accept()

    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_SIZE)
    subscribed = inference_worker_manager.subscribe(stream_id, queue)

    if not subscribed:
        await websocket.send_text(json.dumps({"error": f"No active inference worker for stream {stream_id}"}))
        await websocket.close(code=1000)
        return

    logger.debug("WebSocket client subscribed to stream %d detections", stream_id)

    try:
        while True:
            # Wait for the next detection event (2 s timeout to detect disconnects)
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=2.0)
                await websocket.send_text(json.dumps(payload))
            except TimeoutError:
                # Send a lightweight heartbeat so the browser knows we are alive
                await websocket.send_text(json.dumps({"heartbeat": True, "stream_id": stream_id}))
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected from stream %d", stream_id)
    except Exception as exc:
        logger.warning("WebSocket error for stream %d: %s", stream_id, exc)
    finally:
        inference_worker_manager.unsubscribe(stream_id, queue)


@router.websocket("/workers/stats")
async def ws_worker_stats(websocket: WebSocket):
    """
    Broadcast aggregate inference worker stats every second.

    Useful for a global monitoring dashboard.
    """
    await websocket.accept()
    try:
        while True:
            stats = inference_worker_manager.list_stats()
            await websocket.send_text(json.dumps({"workers": stats}))
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Worker-stats WebSocket error: %s", exc)
