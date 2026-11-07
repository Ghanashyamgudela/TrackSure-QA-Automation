from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import uuid4
from fastapi import Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from applications.database import Base, engine, get_db
from applications.models import Shipment, TrackingHistory
from applications.schemas import (
    ShipmentCreate,
    ShipmentResponse,
    StatusUpdate
)

BASE_DIR = Path(__file__).resolve().parent

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TrackSure Courier API",
    description="Courier and Parcel Tracking Application",
    version="1.0.0"
)
templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)
# Allowed shipment transitions
ALLOWED_NEXT = {
    "BOOKED": "PICKED_UP",
    "PICKED_UP": "IN_TRANSIT",
    "IN_TRANSIT": "OUT_FOR_DELIVERY",
    "OUT_FOR_DELIVERY": "DELIVERED"
}


@app.get("/")
def home():
    return {
        "message": "Welcome to TrackSure Courier System",
        "status": "Running"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# 1. Create Shipment
@app.post("/api/shipments", response_model=ShipmentResponse, status_code=201)
def create_shipment(
    data: ShipmentCreate,
    db: Session = Depends(get_db)
):

    shipment = Shipment(
        tracking_id="TRK-" + uuid4().hex[:10].upper(),
        sender_name=data.sender_name,
        receiver_name=data.receiver_name,
        receiver_address=data.receiver_address,
        parcel_description=data.parcel_description,
        status="BOOKED"
    )

    shipment.history.append(
        TrackingHistory(status="BOOKED")
    )

    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    return shipment


# 2. Get all shipments
@app.get("/api/shipments")
def get_all_shipments(db: Session = Depends(get_db)):

    return db.query(Shipment).all()


# 3. Get shipment by ID
@app.get("/api/shipments/{shipment_id}")
def get_shipment(
    shipment_id: int,
    db: Session = Depends(get_db)
):

    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    return shipment


# 4. Track parcel
@app.get("/api/track/{tracking_id}")
def track_parcel(
    tracking_id: str,
    db: Session = Depends(get_db)
):

    shipment = db.query(Shipment).filter(
        Shipment.tracking_id == tracking_id
    ).first()

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Invalid tracking ID"
        )

    return {
        "tracking_id": shipment.tracking_id,
        "receiver_name": shipment.receiver_name,
        "status": shipment.status,
        "history": [
            {
                "status": item.status,
                "updated_at": item.updated_at
            }
            for item in shipment.history
        ]
    }


# 5. Update shipment status
@app.put("/api/shipments/{shipment_id}/status")
def update_status(
    shipment_id: int,
    data: StatusUpdate,
    db: Session = Depends(get_db)
):

    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    expected_status = ALLOWED_NEXT.get(shipment.status)

    if data.status != expected_status:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition from {shipment.status} to {data.status}"
        )

    shipment.status = data.status

    shipment.history.append(
        TrackingHistory(status=data.status)
    )

    db.commit()
    db.refresh(shipment)

    return {
        "message": "Shipment status updated successfully",
        "tracking_id": shipment.tracking_id,
        "status": shipment.status
    }


# 6. Cancel shipment
@app.post("/api/shipments/{shipment_id}/cancel")
def cancel_shipment(
    shipment_id: int,
    db: Session = Depends(get_db)
):

    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    if shipment.status in ["DELIVERED", "CANCELLED"]:
        raise HTTPException(
            status_code=400,
            detail="Shipment cannot be cancelled"
        )

    shipment.status = "CANCELLED"

    shipment.history.append(
        TrackingHistory(status="CANCELLED")
    )

    db.commit()

    return {
        "message": "Shipment cancelled successfully",
        "tracking_id": shipment.tracking_id,
        "status": shipment.status
    }
    # Dashboard page
@app.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):

    shipments = db.query(Shipment).order_by(
        Shipment.id.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"shipments": shipments}
    )


# Create shipment page
@app.get("/create-shipment")
def create_shipment_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="create_shipment.html",
        context={}
    )


# Tracking page
@app.get("/track")
def tracking_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="tracking.html",
        context={}
    )