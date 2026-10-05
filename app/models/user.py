"""ORM model: maps the Python class to the `users` table."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(100))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)

    # Deleting a user through the ORM also deletes their todos
    todos: Mapped[list["Todo"]] = relationship(  # noqa: F821
        back_populates="owner", cascade="all, delete-orphan"
    )
