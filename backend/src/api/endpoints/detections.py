from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ...api.models.detection import DetectionCreate, DetectionResponse
from ...db.session import get_db
from ...models.camera import Camera
from ...models.detection import Detection
from ...models.stream import Stream
from ...services.detection import ObjectDetectionService

router = APIRouter()
detection_service = ObjectDetectionService()


@router.post("/", response_model=DetectionResponse)
async def create_detection(
    detection: DetectionCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """Create a new detection result."""
    # Verify camera and stream exist
    camera = db.query(Camera).filter(Camera.id == detection.camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    stream = db.query(Stream).filter(Stream.id == detection.stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    # Process frame and perform detection
    frame = detection_service.process_stream(
        camera.rtsp_url,
        camera_type=camera.camera_type,
        device_id=camera.device_id,
        device_path=camera.device_path,
    )
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not process stream")

    detections = detection_service.detect(frame)

    # Store detection results
    db_detection = Detection(
        camera_id=detection.camera_id,
        stream_id=detection.stream_id,
        frame_number=detection.frame_number,
        model_name=detection_service.model_name,
        confidence=detections[0]["confidence"] if detections else 0.0,
        class_name=detections[0]["class_name"] if detections else "",
        bbox=detections[0]["bbox"] if detections else [],
        metadata={"detections": detections},
    )

    db.add(db_detection)
    db.commit()
    db.refresh(db_detection)
    return db_detection


@router.get("/", response_model=list[DetectionResponse])
def list_detections(
    skip: int = 0,
    limit: int = 100,
    camera_id: int | None = None,
    stream_id: int | None = None,
    db: Session = Depends(get_db),
):
    """List all detections with optional filtering."""
    query = db.query(Detection)

    if camera_id:
        query = query.filter(Detection.camera_id == camera_id)
    if stream_id:
        query = query.filter(Detection.stream_id == stream_id)

    detections = query.offset(skip).limit(limit).all()
    return detections


@router.get("/{detection_id}", response_model=DetectionResponse)
def get_detection(detection_id: int, db: Session = Depends(get_db)):
    """Get a specific detection by ID."""
    detection = db.query(Detection).filter(Detection.id == detection_id).first()
    if detection is None:
        raise HTTPException(status_code=404, detail="Detection not found")
    return detection


@router.delete("/{detection_id}")
def delete_detection(detection_id: int, db: Session = Depends(get_db)):
    """Delete a detection."""
    db_detection = db.query(Detection).filter(Detection.id == detection_id).first()
    if db_detection is None:
        raise HTTPException(status_code=404, detail="Detection not found")

    db.delete(db_detection)
    db.commit()
    return {"message": "Detection deleted successfully"}

    db.delete(db_detection)
    db.commit()
    return {"message": "Detection deleted successfully"}
