from fastapi import APIRouter, HTTPException, status
from sqlmodel import select
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List

from app.data.db import SessionDep
from app.models.event import Event
from app.models.user import User
from app.models.registration import Registration

router = APIRouter(prefix="/events", tags=["events"])


class EventCreate(BaseModel):
    """Schema for creating or updating an event (request body validation)."""
    title: str = Field(..., strict=True)
    description: str = Field(..., strict=True)
    date: datetime
    location: str = Field(..., strict=True)


class UserRegister(BaseModel):
    """Schema for the registration request body."""
    username: str = Field(..., strict=True)
    name: str = Field(..., strict=True)
    email: str = Field(..., strict=True)


@router.get("", response_model=List[Event])
def get_events(session: SessionDep) -> List[Event]:
    """
    Retrieve the list of all events in the system.
    """
    statement = select(Event)
    events = session.exec(statement).all()
    return list(events)


@router.post("", response_model=Event, status_code=status.HTTP_201_CREATED)
def create_event(event_in: EventCreate, session: SessionDep) -> Event:
    """
    Create a new event. All fields are required and validated.
    """
    event = Event(
        title=event_in.title,
        description=event_in.description,
        date=event_in.date,
        location=event_in.location,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.get("/{id}", response_model=Event)
def get_event(id: int, session: SessionDep) -> Event:
    """
    Retrieve the details of a specific event by its ID. Raises 404 if not found.
    """
    event = session.get(Event, id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found."
        )
    return event


@router.put("/{id}", response_model=Event)
def update_event(id: int, updated_event: EventCreate, session: SessionDep) -> Event:
    """
    Update an existing event. Raises 404 if the event does not exist.
    """
    db_event = session.get(Event, id)
    if not db_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found."
        )
    db_event.title = updated_event.title
    db_event.description = updated_event.description
    db_event.date = updated_event.date
    db_event.location = updated_event.location
    session.add(db_event)
    session.commit()
    session.refresh(db_event)
    return db_event


@router.post("/{id}/register", status_code=status.HTTP_201_CREATED)
def register_to_event(id: int, user_data: UserRegister, session: SessionDep) -> dict:
    """
    Register a user to the event. Auto-creates the user if they do not exist.
    Raises 404 if the event does not exist, and 400 if the user is already registered.
    """
    # 1. Verify that the event exists
    event = session.get(Event, id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found."
        )

    # 2. Check if the user exists. If not, create them.
    user = session.get(User, user_data.username)
    if not user:
        user = User(
            username=user_data.username,
            name=user_data.name,
            email=user_data.email
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    # 3. Check for duplicate registration
    existing_reg = session.get(Registration, (user.username, id))
    if existing_reg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already registered for this event."
        )

    # 4. Create and persist the registration
    registration = Registration(username=user.username, event_id=id)
    session.add(registration)
    session.commit()
    return {"username": user.username, "event_id": id}


@router.delete("")
def delete_all_events(session: SessionDep) -> dict:
    """
    Delete all events and all registrations.
    """
    regs = session.exec(select(Registration)).all()
    for reg in regs:
        session.delete(reg)
    events = session.exec(select(Event)).all()
    for event in events:
        session.delete(event)
    session.commit()
    return {"message": "All events deleted successfully."}


@router.delete("/{id}")
def delete_event(id: int, session: SessionDep) -> dict:
    """
    Delete a specific event. Also deletes all registrations associated with it.
    Raises 404 if the event does not exist.
    """
    event = session.get(Event, id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found."
        )

    # Cascade delete registrations manually
    regs = session.exec(select(Registration).where(Registration.event_id == id)).all()
    for reg in regs:
        session.delete(reg)

    session.delete(event)
    session.commit()
    return {"message": "Event deleted successfully."}