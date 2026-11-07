from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal
from datetime import datetime


class ShipmentCreate(BaseModel):

    sender_name: str
    receiver_name: str
    receiver_address: str
    parcel_description: str


class ShipmentResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    tracking_id: str
    sender_name: str
    receiver_name: str
    receiver_address: str
    parcel_description: str
    status: str
    created_at: datetime


class DeliveryProofCreate(BaseModel):
    receiver_name: str = Field(min_length=1, max_length=120)
    remarks: str = Field(min_length=1, max_length=2000)
    signature: str | None = Field(default=None, max_length=120)

    @field_validator("receiver_name", "remarks")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class StatusUpdate(BaseModel):

    status: Literal[
        "PICKED_UP",
        "IN_TRANSIT",
        "OUT_FOR_DELIVERY",
        "DELIVERED"
    ]
    delivery_proof: DeliveryProofCreate | None = None


class DelayReasonUpdate(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def require_nonblank_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Delay reason cannot be blank")
        return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class StaffUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: Literal["admin", "operator"]


class StaffUserResponse(BaseModel):
    username: str
    role: str


class TrackingHistoryResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    status: str
    updated_at: datetime