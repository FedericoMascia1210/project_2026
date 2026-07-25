from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    """
    User model representing a registered user in the database.
    """
    __tablename__ = "user"

    username: str = Field(primary_key=True)
    name: str
    email: str