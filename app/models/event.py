from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class Event(SQLModel, table=True):
    """
    Event model representing an event in the database.
    """
    __tablename__ = "event"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str
    date: datetime
    location: str