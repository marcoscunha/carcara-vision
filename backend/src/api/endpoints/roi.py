from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models.roi import RegionOfInterest
from ...schemas.roi import ROICreate, ROIResponse, ROIUpdate

router = APIRouter()


@router.get("/", response_model=list[ROIResponse])
def read_rois(camera_id: int = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Get a list of regions of interest.
    """
    query = db.query(RegionOfInterest)
    if camera_id is not None:
        query = query.filter(RegionOfInterest.camera_id == camera_id)
    rois = query.offset(skip).limit(limit).all()
    return rois


@router.get("/{roi_id}", response_model=ROIResponse)
def read_roi(roi_id: int, db: Session = Depends(get_db)):
    """
    Get a region of interest by its ID.
    """
    roi = db.query(RegionOfInterest).filter(RegionOfInterest.id == roi_id).first()
    if roi is None:
        raise HTTPException(status_code=404, detail="Region of interest not found")
    return roi


@router.post("/", response_model=ROIResponse)
def create_roi(roi: ROICreate, db: Session = Depends(get_db)):
    """
    Create a new region of interest.
    """
    db_roi = RegionOfInterest(**roi.dict())
    db.add(db_roi)
    db.commit()
    db.refresh(db_roi)
    return db_roi


@router.put("/{roi_id}", response_model=ROIResponse)
def update_roi(roi_id: int, roi: ROIUpdate, db: Session = Depends(get_db)):
    """
    Update a region of interest.
    """
    db_roi = db.query(RegionOfInterest).filter(RegionOfInterest.id == roi_id).first()
    if db_roi is None:
        raise HTTPException(status_code=404, detail="Region of interest not found")

    for key, value in roi.dict(exclude_unset=True).items():
        setattr(db_roi, key, value)

    db.commit()
    db.refresh(db_roi)
    return db_roi


@router.delete("/{roi_id}")
def delete_roi(roi_id: int, db: Session = Depends(get_db)):
    """
    Delete a region of interest.
    """
    db_roi = db.query(RegionOfInterest).filter(RegionOfInterest.id == roi_id).first()
    if db_roi is None:
        raise HTTPException(status_code=404, detail="Region of interest not found")

    db.delete(db_roi)
    db.commit()
    return {"message": "Region of interest deleted successfully"}
