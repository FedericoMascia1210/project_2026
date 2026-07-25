from fastapi import APIRouter, HTTPException, status
from sqlmodel import select
from pydantic import BaseModel, Field
from typing import List

from app.data.db import SessionDep
from app.models.user import User
from app.models.registration import Registration

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    username: str = Field(..., strict=True)
    name: str = Field(..., strict=True)
    email: str = Field(..., strict=True)


@router.get("", response_model=List[User])
def get_users(session: SessionDep) -> List[User]:
    """
    Retrieve the list of all registered users.
    """
    statement = select(User)
    users = session.exec(statement).all()
    return list(users)


@router.post("", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, session: SessionDep) -> User:
    """
    Create a new user. Raises a 400 Bad Request if the username is already taken.
    """
    existing_user = session.get(User, user_in.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this username already exists."
        )
    user = User(
        username=user_in.username,
        name=user_in.name,
        email=user_in.email
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.get("/{username}", response_model=User)
def get_user(username: str, session: SessionDep) -> User:
    """
    Retrieve details for a specific user by username. Raises 404 if not found.
    """
    user = session.get(User, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    return user


@router.delete("")
def delete_all_users(session: SessionDep) -> dict:
    """
    Delete all users from the database.
    """
    regs = session.exec(select(Registration)).all()
    for reg in regs:
        session.delete(reg)
    users = session.exec(select(User)).all()
    for user in users:
        session.delete(user)
    session.commit()
    return {"message": "All users deleted successfully."}


@router.delete("/{username}")
def delete_user(username: str, session: SessionDep) -> dict:
    """
    Delete a specific user by username. Also deletes all associated registrations (cascade).
    Raises 404 if user not found.
    """
    user = session.get(User, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    
    # Cascade delete registrations manually
    registrations = session.exec(select(Registration).where(Registration.username == username)).all()
    for reg in registrations:
        session.delete(reg)
    
    session.delete(user)
    session.commit()
    return {"message": "User deleted successfully."}