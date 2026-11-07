from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text
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
    delay_reason = relationship(
        "DelayReason",
        back_populates="shipment",
        uselist=False,
        cascade="all, delete-orphan"
    )
    delivery_proof = relationship(
        "DeliveryProof",
        back_populates="shipment",
        uselist=False,
        cascade="all, delete-orphan"
    )
    audit_log = relationship(
        "StatusAuditLog",
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


class DelayReason(Base):
    __tablename__ = "delay_reasons"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(
        Integer,
        ForeignKey("shipments.id"),
        unique=True,
        nullable=False
    )
    reason = Column(String(500), nullable=False)
    updated_by = Column(String(64), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    shipment = relationship("Shipment", back_populates="delay_reason")


class DeliveryProof(Base):
    __tablename__ = "delivery_proofs"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(
        Integer,
        ForeignKey("shipments.id"),
        unique=True,
        nullable=False
    )
    receiver_name = Column(String(120), nullable=False)
    remarks = Column(Text, nullable=False)
    signature = Column(String(120))
    confirmed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    confirmed_by = Column(String(64), nullable=False)

    shipment = relationship("Shipment", back_populates="delivery_proof")


class StatusAuditLog(Base):
    __tablename__ = "status_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(
        Integer,
        ForeignKey("shipments.id"),
        nullable=False,
        index=True
    )
    previous_status = Column(String(32), nullable=False)
    new_status = Column(String(32), nullable=False)
    changed_by = Column(String(64), nullable=False)
    changed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    shipment = relationship("Shipment", back_populates="audit_log")


class StaffUser(Base):
    __tablename__ = "staff_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), nullable=False, default="operator")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )