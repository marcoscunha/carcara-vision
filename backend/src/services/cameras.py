import asyncio
from collections import defaultdict
from threading import Lock
from typing import TYPE_CHECKING

import cv2

if TYPE_CHECKING:
    from fastapi import WebSocket

from fastapi import WebSocketDisconnect

camera_stream_managers = {"local": defaultdict(list), "remote": defaultdict(list)}

camera_stream_lockers = {"local": defaultdict(Lock), "remote": defaultdict(Lock)}


class CameraStreamException(Exception):
    """Custom exception for camera stream errors."""

    pass


class CameraStream:
    status = "stopped"
    cap = None

    def start_stream(self, camera_device_id: int = None, device_path: str = None):
        with self.lock:
            if device_path:
                import os

                cap = cv2.VideoCapture(os.path.realpath(device_path))
            elif camera_device_id is not None:
                cap = cv2.VideoCapture(camera_device_id)
            else:
                raise CameraStreamException("Either camera_device_id or device_path must be provided.")

            device_label = device_path or str(camera_device_id)
            if not cap.isOpened():
                print("==============================================================================")
                print(f"Failed to open camera {device_label}")
                print("==============================================================================")
                cap.release()
                raise CameraStreamException(f"Camera {device_label} not found or cannot be opened.")

            self.streamer = cap
            self.status = "started"
            print("==============================================================================")
            print(f"STARTING for camera {camera_device_id}")
            print("==============================================================================")

    def stop_stream(self):
        print("==============================================================================")
        print(f"Stopping stream for camera {self.streamer} - cameras {len(self.subscribers)}")
        print("==============================================================================")
        self.streamer.release()
        self.streamer = None
        self.subscribers = []

    def kill_stream(self):
        """Forcefully stop the stream and remove all subscribers."""
        with self.lock:
            print("==============================================================================")
            print(f"Killing stream for camera {self.camera_device_id}")
            print("==============================================================================")
            if self.streamer:
                self.streamer.release()
                self.streamer = None
            self.subscribers.clear()
            self.status = "stopped"


class CameraStreamManager:
    def __init__(self):
        self.streamer = None
        self.subscribers = []
        self.lock = Lock()
        self.status = "stopped"

    def scan_stream(self):
        pass

    def add_stream(self, camera_device_id: int):
        pass

    async def publish_frames(self):
        cap = self.streamer

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            _, buffer = cv2.imencode(".jpg", frame)
            for subscriber in self.subscribers:
                try:
                    await subscriber.send_bytes(buffer.tobytes())
                except WebSocketDisconnect:
                    self.subscribers.remove(subscriber)  # Remove disconnected subscriber
            await asyncio.sleep(1 / 30)

    def add_subscriber(self, callback):
        self.subscribers.append(callback)

    def remove_subscriber(self, websocket: "WebSocket"):
        with self.lock:
            print("==============================================================================")
            print(f" REMOVING SUBSCRIBER  {len(self.subscribers)}")
            print("==============================================================================")
            if websocket in self.subscribers:
                self.subscribers.remove(websocket)  # Remove WebSocket from the list
            if not self.subscribers:
                self.stop_stream()
