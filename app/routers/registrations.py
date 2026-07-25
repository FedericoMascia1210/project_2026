from fastapi import APIRouter, HTTPException, status, Query
from sqlmodel import select
from typing import List

from app.data.db import SessionDep
from app.models.registration import Registration
from app.models.event import Event
from app.models.user import User

router = APIRouter(prefix="/registrations", tags=["registrations"])


@router.get("", response_model=List[Registration])
def get_registrations(session: SessionDep) -> List[Registration]:
    """
    Retrieve the list of all current registrations.
    """
    statement = select(Registration)
    registrations = session.exec(statement).all()
    return list(registrations)


@router.delete("")
def delete_registration(
    username: str = Query(..., description="Username of the registered user"),
    event_id: int = Query(..., description="ID of the registered event"),
    session: SessionDep = None
) -> dict:
    """
    Remove a single registration identified by username and event_id query parameters.
    Raises 404 if the event, user, or registration does not exist.
    """
    # 1. Verify if the event exists
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found."
        )

    # 2. Verify if the user exists
    user = session.get(User, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    # 3. Verify if the registration exists
    registration = session.get(Registration, (username, event_id))
    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration not found."
        )

    # 4. Perform the deletion
    session.delete(registration)
    session.commit()
    return {"message": "Registration deleted successfully."}