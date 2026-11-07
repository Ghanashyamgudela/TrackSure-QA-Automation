from pydantic import BaseModel, ConfigDict
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


class StatusUpdate(BaseModel):

    status: Literal[
        "PICKED_UP",
        "IN_TRANSIT",
        "OUT_FOR_DELIVERY",
        "DELIVERED"
    ]


class TrackingHistoryResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    status: str
    updated_at: datetime