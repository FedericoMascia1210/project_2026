from sqlmodel import create_engine, SQLModel, Session, select
from typing import Annotated
from fastapi import Depends
import os
import random
from datetime import timedelta
from faker import Faker
from app.config import config
# Import all DB models so SQLModel.metadata.create_all detects them
from app.models.registration import Registration  # NOQA
from app.models.event import Event  # NOQA
from app.models.user import User  # NOQA


sqlite_file_name = config.root_dir / "data/database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args, echo=True)


def _seed_database(session: Session) -> None:
    """Populate the database with realistic fake data using Faker.

    Creates 5 random users, 8 random events, and random registrations.
    Called only when the database file does not yet exist.
    """
    fake = Faker("it_IT")

    # --- Create fake users ---
    users: list[User] = []
    for _ in range(5):
        user = User(
            username=fake.unique.user_name(),
            name=fake.name(),
            email=fake.email(),
        )
        session.add(user)
        users.append(user)

    # --- Create fake events ---
    events: list[Event] = []
    for _ in range(8):
        event = Event(
            title=fake.catch_phrase(),
            description=fake.paragraph(nb_sentences=3),
            date=fake.date_time_between(start_date="+1d", end_date="+180d"),
            location=fake.city(),
        )
        session.add(event)
        events.append(event)

    # Flush to assign auto-generated event IDs before creating registrations
    session.flush()

    # --- Create random registrations (many-to-many) ---
    registered_pairs: set[tuple[str, int]] = set()

    # Every user registers to 2–6 random events
    for user in users:
        num_events = random.randint(2, min(6, len(events)))
        chosen_events = random.sample(events, k=num_events)
        for event in chosen_events:
            pair = (user.username, event.id)
            if pair not in registered_pairs:
                registered_pairs.add(pair)
                session.add(Registration(username=user.username, event_id=event.id))

    # Ensure every event has at least 2 attendees
    for event in events:
        attendees = [p[0] for p in registered_pairs if p[1] == event.id]
        if len(attendees) < 2:
            available = [u for u in users if u.username not in attendees]
            for extra_user in random.sample(available, k=min(2 - len(attendees), len(available))):
                pair = (extra_user.username, event.id)
                registered_pairs.add(pair)
                session.add(Registration(username=extra_user.username, event_id=event.id))

    session.commit()


def init_database() -> None:
    """Initialise the database: create tables and seed with fake data on first run."""
    ds_exists = os.path.isfile(sqlite_file_name)
    SQLModel.metadata.create_all(engine)
    if not ds_exists:
        with Session(engine) as session:
            _seed_database(session)


def get_session():
    """Yield a SQLModel session for dependency injection in FastAPI routes."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]