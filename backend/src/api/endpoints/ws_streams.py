import asyncio

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models.stream import Stream
from ...services.cameras import CameraStreamManager
from ...services.cameras import camera_stream_lockers
from ...services.cameras import camera_stream_managers

router = APIRouter()


@router.websocket("/{stream_id}")
async def stream_camera(websocket: WebSocket,
                        stream_id: int,
                        db: Session = Depends(get_db)):
    await websocket.accept()
    try:
        # Retrieve the camera_id associated with the stream_id
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream:
            raise HTTPException(status_code=404, detail="Stream not found")

        # Ensure the camera is local
        if stream.camera.camera_type != "local":
            raise HTTPException(status_code=400, detail="Only local cameras are supported")

        camera_device_id = stream.camera.device_id

        # Safely access or create the CameraStreamManager
        with camera_stream_lockers["local"][camera_device_id]:
            camera_stream_manager = camera_stream_managers["local"].get(camera_device_id)
            if camera_stream_manager is None:
                # Create a new CameraStreamManager if it doesn't exist
                camera_stream_manager = CameraStreamManager(camera_device_id)
                camera_stream_managers["local"][camera_device_id] = camera_stream_manager

            # if len(camera_stream_manager.subscribers) == 0:
                camera_stream_manager.start_stream(camera_device_id)

            # Add the subscriber to the manager
            camera_stream_manager.add_subscriber(websocket)

        # If there is just one subscriber, start the frame publishing
        if len(camera_stream_manager.subscribers) == 1:
            await camera_stream_manager.publish_frames()
        else:
            # If there are multiple subscribers, just wait for the frames to be published
            while True:
                await asyncio.sleep(1)
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        # Print the trace of the error
        import traceback
        traceback.print_exc()
        print(f"Error in WebSocket stream: {e}")
    finally:
        # Remove the subscriber and close the WebSocket
        camera_stream_manager.remove_subscriber(websocket)
        await websocket.close()


@router.delete("/kill/{camera_device_id}")
async def kill_camera_stream(camera_device_id: int):
    """Endpoint to kill a specific camera stream."""
    with camera_stream_lockers["local"][camera_device_id]:
        camera_stream_manager = camera_stream_managers["local"].get(camera_device_id)
        if camera_stream_manager:
            camera_stream_manager.kill_stream()
            del camera_stream_managers["local"][camera_device_id]
            return {"message": f"Stream for camera {camera_device_id} has been killed."}
        else:
            raise HTTPException(status_code=404, detail="Stream not found")
