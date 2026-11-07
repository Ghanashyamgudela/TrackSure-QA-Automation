
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from applications.database import Base
from applications.models import Shipment, TrackingHistory


@pytest.fixture
def db_session():

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )

    Base.metadata.create_all(bind=engine)

    TestingSession = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )

    session = TestingSession()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_shipment_saved_in_database(db_session):

    shipment = Shipment(
        tracking_id="TRK-TEST001",
        sender_name="Rahul",
        receiver_name="Arjun",
        receiver_address="Vijayawada",
        parcel_description="Laptop Accessories",
        status="BOOKED"
    )

    db_session.add(shipment)
    db_session.commit()

    saved_shipment = db_session.query(Shipment).filter_by(
        tracking_id="TRK-TEST001"
    ).first()

    assert saved_shipment is not None
    assert saved_shipment.sender_name == "Rahul"
    assert saved_shipment.status == "BOOKED"


def test_tracking_history_saved(db_session):

    shipment = Shipment(
        tracking_id="TRK-TEST002",
        sender_name="Rahul",
        receiver_name="Arjun",
        receiver_address="Vijayawada",
        parcel_description="Mobile Phone",
        status="BOOKED"
    )

    db_session.add(shipment)
    db_session.commit()

    history = TrackingHistory(
        shipment_id=shipment.id,
        status="BOOKED"
    )

    db_session.add(history)
    db_session.commit()

    saved_history = db_session.query(
        TrackingHistory
    ).filter_by(shipment_id=shipment.id).all()

    assert len(saved_history) == 1
    assert saved_history[0].status == "BOOKED"


def test_shipment_tracking_id_is_unique(db_session):

    shipment1 = Shipment(
        tracking_id="TRK-UNIQUE",
        sender_name="Rahul",
        receiver_name="Arjun",
        receiver_address="Vijayawada",
        parcel_description="Books",
        status="BOOKED"
    )

    shipment2 = Shipment(
        tracking_id="TRK-UNIQUE",
        sender_name="Kiran",
        receiver_name="Ravi",
        receiver_address="Hyderabad",
        parcel_description="Clothes",
        status="BOOKED"
    )

    db_session.add(shipment1)
    db_session.commit()

    db_session.add(shipment2)

    with pytest.raises(Exception):
        db_session.commit()
