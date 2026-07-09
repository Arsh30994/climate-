from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Region
from app.schemas import RegionCreate, RegionOut

router = APIRouter(prefix="/api/regions", tags=["Problem Definition"])


@router.get("", response_model=List[RegionOut])
def list_regions(db: Session = Depends(get_db)):
    return db.query(Region).order_by(Region.id).all()


@router.post("", response_model=RegionOut, status_code=201)
def create_region(payload: RegionCreate, db: Session = Depends(get_db)):
    existing = db.query(Region).filter(Region.name == payload.name).first()
    if existing:
        raise HTTPException(409, f"Region '{payload.name}' already exists.")
    region = Region(**payload.model_dump())
    db.add(region)
    db.commit()
    db.refresh(region)
    return region


@router.get("/{region_id}", response_model=RegionOut)
def get_region(region_id: int, db: Session = Depends(get_db)):
    region = db.query(Region).get(region_id)
    if region is None:
        raise HTTPException(404, "Region not found.")
    return region
