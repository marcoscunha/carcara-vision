"""WebSocket endpoint for real-time alarm events.

Clients connect to::

    WS /api/v1/ws/alarms

and receive alarm lifecycle events emitted by the ``AlarmDispatcher``.

Message types
-------------

``alarm.opened``::

    {
        "type":            "alarm.opened",
        "alarm_id":        int,
        "stream_id":       int,
        "zone_id":         int | null,
        "event_id":        int | null,
        "timestamp":       float,
        "severity":        "info" | "warning" | "critical",
        "alarm_name":      str,
        "matched_classes": {class_name: count, ...},
        "peak_confidence": float,
        "peak_count":      int
    }

``alarm.closed``::

    Same fields, ``type`` = ``"alarm.closed"``.

``heartbeat``::

    {"heartbeat": true}
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...services.alarm_dispatcher import alarm_dispatcher

logger = logging.getLogger(__name__)

router = APIRouter()

_QUEUE_SIZE = 200  # buffer size before dropping oldest


@router.websocket("/alarms")
async def ws_alarms(websocket: WebSocket) -> None:
    """Stream real-time alarm events to a WebSocket client."""
    await websocket.accept()
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=_QUEUE_SIZE)
    alarm_dispatcher.add_ws_subscriber(queue)
    logger.debug("WebSocket client subscribed to alarms")
    try:
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                await websocket.send_text(json.dumps(payload))
            except TimeoutError:
                await websocket.send_text(json.dumps({"heartbeat": True}))
    except WebSocketDisconnect:
        logger.debug("WebSocket alarm client disconnected")
    except Exception as exc:
        logger.warning("WebSocket alarm error: %s", exc)
    finally:
        alarm_dispatcher.remove_ws_subscriber(queue)
