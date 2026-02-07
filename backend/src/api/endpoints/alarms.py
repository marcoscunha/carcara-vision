from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models.alarm import Alarm
from ...schemas.alarm import AlarmCreate, AlarmResponse, AlarmUpdate

router = APIRouter()


@router.get("/", response_model=list[AlarmResponse])
def read_alarms(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Get a list of alarms.
    """
    alarms = db.query(Alarm).offset(skip).limit(limit).all()
    return alarms


@router.get("/{alarm_id}", response_model=AlarmResponse)
def read_alarm(alarm_id: int, db: Session = Depends(get_db)):
    """
    Get an alarm by its ID.
    """
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if alarm is None:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return alarm


@router.post("/", response_model=AlarmResponse)
def create_alarm(alarm: AlarmCreate, db: Session = Depends(get_db)):
    """
    Create a new alarm.
    """
    db_alarm = Alarm(**alarm.dict())
    db.add(db_alarm)
    db.commit()
    db.refresh(db_alarm)
    return db_alarm


@router.put("/{alarm_id}", response_model=AlarmResponse)
def update_alarm(alarm_id: int, alarm: AlarmUpdate, db: Session = Depends(get_db)):
    """
    Update an alarm.
    """
    db_alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if db_alarm is None:
        raise HTTPException(status_code=404, detail="Alarm not found")

    for key, value in alarm.dict(exclude_unset=True).items():
        setattr(db_alarm, key, value)

    db.commit()
    db.refresh(db_alarm)
    return db_alarm


@router.delete("/{alarm_id}")
def delete_alarm(alarm_id: int, db: Session = Depends(get_db)):
    """
    Delete an alarm.
    """
    db_alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if db_alarm is None:
        raise HTTPException(status_code=404, detail="Alarm not found")

    db.delete(db_alarm)
    db.commit()
    return {"message": "Alarm deleted successfully"}
