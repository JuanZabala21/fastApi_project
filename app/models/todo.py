"""ORM model: the `todos` table. Each todo belongs to one user (foreign key)."""
from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    done: Mapped[bool] = mapped_column(default=False)
    # The day the user plans to do it (optional). Date only, no time.
    due_date: Mapped[date | None] = mapped_column(Date, index=True, default=None)
    # "low" | "medium" | "high". A plain string (validated by Pydantic) avoids a database enum type,
    # which is painful to change later.
    priority: Mapped[str] = mapped_column(String(6), default="medium", server_default="medium")
    # ondelete=CASCADE: if the user row is deleted, the database removes their todos too
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    owner: Mapped["User"] = relationship(back_populates="todos")  # noqa: F821
