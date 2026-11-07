import csv
import io
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from applications.database import Base, engine, get_db
from applications.models import (
    DelayReason,
    DeliveryProof,
    Shipment,
    StaffUser,
    StatusAuditLog,
    TrackingHistory,
)
from applications.schemas import (
    DelayReasonUpdate,
    LoginRequest,
    ShipmentCreate,
    ShipmentResponse,
    StaffUserCreate,
    StatusUpdate,
)
from applications.security import (
    CSRF_COOKIE,
    clear_login_cookies,
    get_current_user,
    get_optional_user,
    get_secret_key,
    hash_password,
    require_admin,
    require_operator,
    set_login_cookies,
    verify_csrf,
    verify_password,
)

BASE_DIR = Path(__file__).resolve().parent
DELAY_AFTER = timedelta(hours=24)
ESTIMATED_DELIVERY_DAYS = 5
FINAL_STATUSES = {"DELIVERED", "CANCELLED"}
TIMELINE_STATUSES = (
    "BOOKED",
    "PICKED_UP",
    "IN_TRANSIT",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
)

Base.metadata.create_all(bind=engine)

ALLOWED_NEXT = {
    "BOOKED": "PICKED_UP",
    "PICKED_UP": "IN_TRANSIT",
    "IN_TRANSIT": "OUT_FOR_DELIVERY",
    "OUT_FOR_DELIVERY": "DELIVERED",
}


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def shipment_last_movement(shipment: Shipment) -> datetime:
    if shipment.history:
        return max(utc_datetime(item.updated_at) for item in shipment.history)
    return utc_datetime(shipment.created_at)


def is_delayed(shipment: Shipment, now: datetime | None = None) -> bool:
    if shipment.status in FINAL_STATUSES:
        return False
    current_time = now or datetime.now(timezone.utc)
    return current_time - shipment_last_movement(shipment) >= DELAY_AFTER


def record_status_change(
    db: Session,
    shipment: Shipment,
    previous_status: str,
    username: str,
) -> None:
    shipment.history.append(TrackingHistory(status=shipment.status))
    shipment.audit_log.append(
        StatusAuditLog(
            previous_status=previous_status,
            new_status=shipment.status,
            changed_by=username,
        )
    )


def bootstrap_admin() -> None:
    username = os.environ.get("TRACKSURE_BOOTSTRAP_ADMIN_USERNAME", "").strip()
    password = os.environ.get("TRACKSURE_BOOTSTRAP_ADMIN_PASSWORD", "")
    if bool(username) != bool(password):
        raise RuntimeError(
            "Set both TRACKSURE_BOOTSTRAP_ADMIN_USERNAME and "
            "TRACKSURE_BOOTSTRAP_ADMIN_PASSWORD to bootstrap the administrator."
        )
    if not username:
        return
    if len(password) < 12:
        raise RuntimeError("The bootstrap administrator password must be at least 12 characters.")
    get_secret_key()
    with Session(engine) as db:
        admin = db.query(StaffUser).filter(StaffUser.username == username).first()
        if admin is None:
            db.add(
                StaffUser(
                    username=username,
                    password_hash=hash_password(password),
                    role="admin",
                    is_active=True,
                )
            )
            db.commit()
        elif admin.role != "admin" or not admin.is_active:
            admin.role = "admin"
            admin.is_active = True
            db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    bootstrap_admin()
    yield


app = FastAPI(
    title="TrackSure Courier API",
    description="Courier and Parcel Tracking Application",
    version="2.0.0",
    lifespan=lifespan,
)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_model=dict[str, str])
def home() -> dict[str, str]:
    return {"message": "Welcome to TrackSure Courier System", "status": "Running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/auth/csrf")
def csrf_token(request: Request) -> dict[str, str]:
    token = request.cookies.get(CSRF_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Login required")
    return {"csrf_token": token}


@app.post("/api/auth/login")
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    get_secret_key()
    user = db.query(StaffUser).filter(StaffUser.username == data.username).first()
    if user is None or not user.is_active or not verify_password(
        data.password, user.password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    csrf = set_login_cookies(response, user.id, request)
    return {"username": user.username, "role": user.role, "csrf_token": csrf}


@app.post("/api/auth/logout")
def logout(
    request: Request,
    response: Response,
    user: StaffUser = Depends(get_current_user),
) -> dict[str, str]:
    del user
    verify_csrf(request)
    clear_login_cookies(response, request)
    return {"message": "Logged out"}


@app.get("/api/auth/me")
def current_user(
    user: StaffUser | None = Depends(get_optional_user),
) -> dict[str, str | bool | None]:
    if user is None:
        return {"authenticated": False, "username": None, "role": None}
    return {
        "authenticated": True,
        "username": user.username,
        "role": user.role,
    }


@app.post("/api/admin/users", status_code=201)
def create_staff_user(
    data: StaffUserCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: StaffUser = Depends(require_admin),
) -> dict[str, str]:
    verify_csrf(request)
    if db.query(StaffUser).filter(StaffUser.username == data.username).first():
        raise HTTPException(status_code=409, detail="Username already exists")
    user = StaffUser(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return {"username": user.username, "role": user.role}


@app.get("/api/admin/users")
def list_staff_users(
    admin: StaffUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    del admin
    users = db.query(StaffUser).order_by(StaffUser.username).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active,
        }
        for user in users
    ]


@app.patch("/api/admin/users/{user_id}/active")
def set_staff_user_active(
    user_id: int,
    active: bool,
    request: Request,
    db: Session = Depends(get_db),
    admin: StaffUser = Depends(require_admin),
) -> dict[str, object]:
    verify_csrf(request)
    user = db.query(StaffUser).filter(StaffUser.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Staff user not found")
    if user.id == admin.id and not active:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if not active and user.role == "admin":
        active_admins = (
            db.query(StaffUser)
            .filter(StaffUser.role == "admin", StaffUser.is_active.is_(True))
            .count()
        )
        if active_admins <= 1:
            raise HTTPException(
                status_code=400,
                detail="At least one active administrator must remain",
            )
    user.is_active = active
    db.commit()
    return {"username": user.username, "is_active": user.is_active}


@app.post("/api/shipments", response_model=ShipmentResponse, status_code=201)
def create_shipment(
    data: ShipmentCreate,
    db: Session = Depends(get_db),
) -> Shipment:
    shipment = Shipment(
        tracking_id="TRK-" + uuid4().hex[:10].upper(),
        sender_name=data.sender_name,
        receiver_name=data.receiver_name,
        receiver_address=data.receiver_address,
        parcel_description=data.parcel_description,
        status="BOOKED",
    )
    db.add(shipment)
    db.flush()
    shipment.history.append(TrackingHistory(status="BOOKED"))
    shipment.audit_log.append(
        StatusAuditLog(
            previous_status="NONE",
            new_status="BOOKED",
            changed_by="public:shipment-creation",
        )
    )
    db.commit()
    db.refresh(shipment)
    return shipment


def shipment_query(
    db: Session,
    q: str,
    status: str,
    sort_by: str,
    order: str,
):
    allowed_statuses = FINAL_STATUSES | set(TIMELINE_STATUSES) | {"CANCELLED"}
    if status and status not in allowed_statuses:
        raise HTTPException(status_code=422, detail="Unknown shipment status")
    if sort_by not in {"created_at", "tracking_id", "status"}:
        raise HTTPException(status_code=422, detail="sort_by must be created_at, tracking_id, or status")
    if order not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail="order must be asc or desc")

    query = db.query(Shipment)
    if q:
        value = f"%{q.strip()}%"
        query = query.filter(
            Shipment.tracking_id.ilike(value)
            | Shipment.sender_name.ilike(value)
            | Shipment.receiver_name.ilike(value)
        )
    if status:
        query = query.filter(Shipment.status == status)
    column = getattr(Shipment, sort_by)
    ordering = column.asc() if order == "asc" else column.desc()
    return query.order_by(ordering, Shipment.id.desc())


def csv_safe(value: str) -> str:
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@app.get("/api/shipments/export.csv")
def export_shipments_csv(
    db: Session = Depends(get_db),
    q: str = "",
    status: str = "",
    sort_by: str = "created_at",
    order: str = "desc",
) -> StreamingResponse:
    shipments = shipment_query(db, q, status, sort_by, order).all()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "tracking_id",
            "sender_name",
            "receiver_name",
            "receiver_address",
            "parcel_description",
            "status",
            "created_at",
        ]
    )
    for shipment in shipments:
        writer.writerow(
            [
                csv_safe(shipment.tracking_id),
                csv_safe(shipment.sender_name),
                csv_safe(shipment.receiver_name),
                csv_safe(shipment.receiver_address),
                csv_safe(shipment.parcel_description),
                csv_safe(shipment.status),
                utc_datetime(shipment.created_at).isoformat(),
            ]
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="tracksure_shipments.csv"'},
    )


@app.get("/api/shipments")
def get_all_shipments(
    db: Session = Depends(get_db),
    q: str = "",
    status: str = "",
    sort_by: str = "created_at",
    order: str = "desc",
):
    return shipment_query(db, q, status, sort_by, order).all()


@app.get("/api/shipments/{shipment_id}")
def get_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment


@app.get("/api/track/{tracking_id}")
def track_parcel(
    tracking_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    shipment = (
        db.query(Shipment)
        .options(
            joinedload(Shipment.history),
            joinedload(Shipment.delivery_proof),
        )
        .filter(Shipment.tracking_id == tracking_id)
        .first()
    )
    if shipment is None:
        raise HTTPException(status_code=404, detail="Invalid tracking ID")

    history = sorted(shipment.history, key=lambda item: utc_datetime(item.updated_at))
    status_dates = {
        item.status: utc_datetime(item.updated_at).isoformat()
        for item in history
    }
    status_dates.setdefault("BOOKED", utc_datetime(shipment.created_at).isoformat())
    timeline = [
        {
            "status": status,
            "updated_at": status_dates.get(status),
            "completed": status in status_dates,
            "current": status == shipment.status,
        }
        for status in TIMELINE_STATUSES
    ]
    if shipment.status == "CANCELLED":
        timeline.append(
            {
                "status": "CANCELLED",
                "updated_at": status_dates.get("CANCELLED"),
                "completed": True,
                "current": True,
            }
        )

    proof = None
    if shipment.delivery_proof:
        proof = {
            "receiver_name": shipment.delivery_proof.receiver_name,
            "remarks": shipment.delivery_proof.remarks,
            "confirmed_at": utc_datetime(
                shipment.delivery_proof.confirmed_at
            ).isoformat(),
        }
    return {
        "tracking_id": shipment.tracking_id,
        "sender_name": shipment.sender_name,
        "receiver_name": shipment.receiver_name,
        "receiver_address": shipment.receiver_address,
        "parcel_description": shipment.parcel_description,
        "status": shipment.status,
        "history": [
            {
                "status": item.status,
                "updated_at": utc_datetime(item.updated_at).isoformat(),
            }
            for item in history
        ],
        "timeline": timeline,
        "estimated_delivery": (
            utc_datetime(shipment.created_at)
            + timedelta(days=ESTIMATED_DELIVERY_DAYS)
        ).isoformat(),
        "delivery_proof": proof,
    }


@app.get("/api/shipments/{shipment_id}/audit")
def shipment_audit_log(
    shipment_id: int,
    user: StaffUser = Depends(require_operator),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    del user
    if db.query(Shipment.id).filter(Shipment.id == shipment_id).first() is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    entries = (
        db.query(StatusAuditLog)
        .filter(StatusAuditLog.shipment_id == shipment_id)
        .order_by(StatusAuditLog.changed_at.asc(), StatusAuditLog.id.asc())
        .all()
    )
    return [
        {
            "previous_status": entry.previous_status,
            "new_status": entry.new_status,
            "changed_by": entry.changed_by,
            "changed_at": utc_datetime(entry.changed_at).isoformat(),
        }
        for entry in entries
    ]


@app.get("/api/alerts/delayed")
def delayed_shipments(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    now = datetime.now(timezone.utc)
    shipments = (
        db.query(Shipment)
        .options(joinedload(Shipment.history), joinedload(Shipment.delay_reason))
        .filter(Shipment.status.notin_(FINAL_STATUSES))
        .all()
    )
    alerts = []
    for shipment in shipments:
        last_movement = shipment_last_movement(shipment)
        if is_delayed(shipment, now):
            alerts.append(
                {
                    "tracking_id": shipment.tracking_id,
                    "status": shipment.status,
                    "last_movement": last_movement.isoformat(),
                    "delayed_hours": round((now - last_movement).total_seconds() / 3600, 1),
                    "reason": shipment.delay_reason.reason if shipment.delay_reason else None,
                }
            )
    return alerts


@app.put("/api/shipments/{shipment_id}/delay-reason")
def update_delay_reason(
    shipment_id: int,
    data: DelayReasonUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: StaffUser = Depends(require_operator),
) -> dict[str, str]:
    verify_csrf(request)
    shipment = (
        db.query(Shipment)
        .options(joinedload(Shipment.history), joinedload(Shipment.delay_reason))
        .filter(Shipment.id == shipment_id)
        .first()
    )
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if not is_delayed(shipment):
        raise HTTPException(status_code=400, detail="Shipment is not currently delayed")
    reason = shipment.delay_reason
    if reason is None:
        reason = DelayReason(shipment_id=shipment.id, reason=data.reason.strip(), updated_by=user.username)
        db.add(reason)
    else:
        reason.reason = data.reason.strip()
        reason.updated_by = user.username
    if not reason.reason:
        raise HTTPException(status_code=422, detail="Delay reason cannot be blank")
    db.commit()
    return {"tracking_id": shipment.tracking_id, "reason": reason.reason}


@app.get("/api/analytics")
def shipment_analytics(db: Session = Depends(get_db)) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    shipments = db.query(Shipment).options(joinedload(Shipment.history)).all()
    total = len(shipments)
    booked_count = sum(shipment.status == "BOOKED" for shipment in shipments)
    delivered = sum(shipment.status == "DELIVERED" for shipment in shipments)
    in_transit = sum(
        shipment.status in {"PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY"}
        for shipment in shipments
    )
    delayed = sum(is_delayed(shipment, now) for shipment in shipments)
    status_counts: dict[str, int] = {}
    for shipment in shipments:
        status_counts[shipment.status] = status_counts.get(shipment.status, 0) + 1

    start_date = now.date() - timedelta(days=6)
    weekly_counts = { (start_date + timedelta(days=offset)).isoformat(): 0 for offset in range(7) }
    for shipment in shipments:
        booking_date = utc_datetime(shipment.created_at).date()
        if booking_date.isoformat() in weekly_counts:
            weekly_counts[booking_date.isoformat()] += 1

    activity = sorted(
        (
            {
                "tracking_id": shipment.tracking_id,
                "receiver_name": shipment.receiver_name,
                "status": item.status,
                "updated_at": utc_datetime(item.updated_at).isoformat(),
            }
            for shipment in shipments
            for item in shipment.history
        ),
        key=lambda item: item["updated_at"],
        reverse=True,
    )[:8]

    return {
        "total": total,
        "booked": booked_count,
        "delivered": delivered,
        "in_transit": in_transit,
        "delayed": delayed,
        "delivery_success_percentage": round(delivered / total * 100, 1) if total else 0.0,
        "weekly_shipments": [
            {"date": day, "count": count} for day, count in weekly_counts.items()
        ],
        "status_distribution": status_counts,
        "recent_activity": activity,
    }


@app.put("/api/shipments/{shipment_id}/status")
def update_status(
    shipment_id: int,
    data: StatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: StaffUser = Depends(require_operator),
) -> dict[str, str]:
    verify_csrf(request)
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")

    expected_status = ALLOWED_NEXT.get(shipment.status)
    if data.status != expected_status:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition from {shipment.status} to {data.status}",
        )
    if data.status == "DELIVERED" and data.delivery_proof is None:
        raise HTTPException(
            status_code=422,
            detail="Delivery confirmation is required to mark a shipment delivered",
        )
    if data.status != "DELIVERED" and data.delivery_proof is not None:
        raise HTTPException(
            status_code=422,
            detail="Delivery confirmation is only accepted for DELIVERED status",
        )

    previous_status = shipment.status
    shipment.status = data.status
    record_status_change(db, shipment, previous_status, user.username)
    if data.delivery_proof is not None:
        db.add(
            DeliveryProof(
                shipment_id=shipment.id,
                receiver_name=data.delivery_proof.receiver_name.strip(),
                remarks=data.delivery_proof.remarks.strip(),
                signature=(
                    data.delivery_proof.signature.strip()
                    if data.delivery_proof.signature
                    else None
                ),
                confirmed_by=user.username,
            )
        )
    db.commit()
    return {
        "message": "Shipment status updated successfully",
        "tracking_id": shipment.tracking_id,
        "status": shipment.status,
    }


@app.post("/api/shipments/{shipment_id}/cancel")
def cancel_shipment(
    shipment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: StaffUser = Depends(require_operator),
) -> dict[str, str]:
    verify_csrf(request)
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if shipment.status in FINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Shipment cannot be cancelled")
    previous_status = shipment.status
    shipment.status = "CANCELLED"
    record_status_change(db, shipment, previous_status, user.username)
    db.commit()
    return {
        "message": "Shipment cancelled successfully",
        "tracking_id": shipment.tracking_id,
        "status": shipment.status,
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    shipments = db.query(Shipment).order_by(Shipment.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"shipments": shipments, "active_nav": "dashboard"},
    )


@app.get("/shipments", response_class=HTMLResponse)
def all_shipments_page(request: Request, db: Session = Depends(get_db)) -> Response:
    shipments = db.query(Shipment).order_by(Shipment.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"shipments": shipments, "active_nav": "shipments"},
    )


@app.get("/create-shipment", response_class=HTMLResponse)
def create_shipment_page(request: Request) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="create_shipment.html",
        context={"active_nav": "create"},
    )


@app.get("/track", response_class=HTMLResponse)
def tracking_page(request: Request) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="tracking.html",
        context={
            "tracking_id": request.query_params.get("tracking_id", ""),
            "active_nav": "track",
        },
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"active_nav": ""},
    )


@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context={"active_nav": "reports"},
    )


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"active_nav": "settings"},
    )
