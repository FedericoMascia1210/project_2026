import sys
from pathlib import Path
import argparse
import random

# Add project root to sys.path to allow running directly
sys.path.append(str(Path(__file__).resolve().parent.parent))

from faker import Faker
from sqlmodel import Session, SQLModel
from app.data.db import engine
from app.models.user import User
from app.models.event import Event
from app.models.registration import Registration


def seed_db(num_users: int, num_events: int, reset: bool) -> None:
    """Seed the database with a specific number of random users and events using Faker.

    Args:
        num_users: Number of fake users to generate.
        num_events: Number of fake events to generate.
        reset: If True, drops all database tables and recreates them first.
    """
    fake = Faker("it_IT")

    if reset:
        print("Resetting database (dropping all tables)...")
        SQLModel.metadata.drop_all(engine)
        print("Recreating database tables...")
        SQLModel.metadata.create_all(engine)
    else:
        # Just create tables if they do not exist
        SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        print(f"Generating {num_users} fake users...")
        users: list[User] = []
        for _ in range(num_users):
            user = User(
                username=fake.unique.user_name(),
                name=fake.name(),
                email=fake.email(),
            )
            session.add(user)
            users.append(user)

        print(f"Generating {num_events} fake events...")
        events: list[Event] = []
        for _ in range(num_events):
            event = Event(
                title=fake.catch_phrase(),
                description=fake.paragraph(nb_sentences=3),
                date=fake.date_time_between(start_date="+1d", end_date="+180d"),
                location=fake.city(),
            )
            session.add(event)
            events.append(event)

        # Flush to get the IDs of events (autoincrement)
        session.flush()

        # Check if we have users and events to create registrations
        if users and events:
            print("Generating random registrations (many-to-many)...")
            registered_pairs: set[tuple[str, int]] = set()

            # Every user registers to 1–5 random events
            for user in users:
                k = random.randint(1, min(len(events), 5))
                chosen_events = random.sample(events, k=k)
                for event in chosen_events:
                    pair = (user.username, event.id)
                    if pair not in registered_pairs:
                        registered_pairs.add(pair)
                        session.add(Registration(username=user.username, event_id=event.id))

            # Ensure every event has at least 1 attendee if we have users
            for event in events:
                attendees = [p[0] for p in registered_pairs if p[1] == event.id]
                if not attendees:
                    extra_user = random.choice(users)
                    pair = (extra_user.username, event.id)
                    registered_pairs.add(pair)
                    session.add(Registration(username=extra_user.username, event_id=event.id))

        session.commit()
        print("Database successfully seeded!")


def main() -> None:
    """Parse command line arguments and execute the seeding process."""
    parser = argparse.ArgumentParser(description="Populate the database with random users and events.")
    parser.add_argument(
        "-u", "--users",
        type=int,
        default=10,
        help="Number of users to generate (default: 10)"
    )
    parser.add_argument(
        "-e", "--events",
        type=int,
        default=15,
        help="Number of events to generate (default: 15)"
    )
    parser.add_argument(
        "-r", "--reset",
        action="store_true",
        help="Reset the database (drop and recreate tables) before seeding"
    )

    args = parser.parse_args()
    seed_db(num_users=args.users, num_events=args.events, reset=args.reset)


if __name__ == "__main__":
    main()
