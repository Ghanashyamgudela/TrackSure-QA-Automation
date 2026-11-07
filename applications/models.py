from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from applications.database import Base


class Shipment(Base):

    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)

    tracking_id = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    sender_name = Column(String, nullable=False)
    receiver_name = Column(String, nullable=False)
    receiver_address = Column(String, nullable=False)

    parcel_description = Column(String, nullable=False)

    status = Column(
        String,
        default="BOOKED",
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    history = relationship(
        "TrackingHistory",
        back_populates="shipment",
        cascade="all, delete-orphan"
    )


class TrackingHistory(Base):

    __tablename__ = "tracking_history"

    id = Column(Integer, primary_key=True, index=True)

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.id"),
        nullable=False
    )

    status = Column(String, nullable=False)

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    shipment = relationship(
        "Shipment",
        back_populates="history"
    )