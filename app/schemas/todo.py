"""Pydantic models: request/response validation and serialization."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.text import clean_text

Priority = Literal["low", "medium", "high"]


def _clean_title(value: str) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        raise ValueError("title can't be empty")
    return cleaned


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    done: bool = False
    due_date: date | None = None
    priority: Priority = "medium"

    _clean_title = field_validator("title")(_clean_title)  # strips hidden characters


class TodoUpdate(BaseModel):
    # All optional so clients can send partial updates (PATCH).
    # due_date: send null to clear it; leave it out to keep it.
    title: str | None = Field(default=None, min_length=1, max_length=100)
    done: bool | None = None
    due_date: date | None = None
    priority: Priority | None = None

    @field_validator("title", "done", "priority")
    @classmethod
    def not_null(cls, value):
        # These columns are NOT NULL: an explicit null would otherwise end in a 500 from the database
        if value is None:
            raise ValueError("cannot be null")
        return value

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return _clean_title(value)


class Todo(TodoCreate):
    model_config = ConfigDict(from_attributes=True)  # allows building it from an ORM object

    id: int
