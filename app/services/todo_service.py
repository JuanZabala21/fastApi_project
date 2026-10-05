"""Todo business logic. Every query is scoped to an owner so users can't see each other's todos."""
from datetime import date
from typing import Literal

from sqlalchemy import case, select
from sqlalchemy import delete as sql_delete  # our own delete() below would shadow it
from sqlalchemy.orm import Session

from app.models.todo import Todo
from app.schemas.todo import TodoCreate, TodoUpdate

SortBy = Literal["id", "due_date", "priority"]

_PRIORITY_RANK = case({"high": 0, "medium": 1, "low": 2}, value=Todo.priority, else_=3)


def get_owned(db: Session, todo_id: int, user_id: int) -> Todo | None:
    """Returns the todo only if it exists AND belongs to `user_id`."""
    return db.scalar(select(Todo).where(Todo.id == todo_id, Todo.user_id == user_id))


def list_owned(
    db: Session,
    user_id: int,
    done: bool | None = None,
    limit: int = 10,
    priority: str | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    overdue: bool = False,
    has_due_date: bool | None = None,
    sort_by: SortBy = "id",
) -> list[Todo]:
    query = select(Todo).where(Todo.user_id == user_id).limit(limit)
    if done is not None:
        query = query.where(Todo.done == done)
    if priority is not None:
        query = query.where(Todo.priority == priority)
    if due_from is not None:
        query = query.where(Todo.due_date >= due_from)
    if due_to is not None:
        query = query.where(Todo.due_date <= due_to)
    if overdue:  # past due and still pending
        query = query.where(Todo.due_date < date.today(), Todo.done.is_(False))
    if has_due_date is not None:
        query = query.where(Todo.due_date.is_not(None) if has_due_date else Todo.due_date.is_(None))

    if sort_by == "due_date":  # soonest first, undated last
        query = query.order_by(Todo.due_date.is_(None), Todo.due_date, _PRIORITY_RANK, Todo.id)
    elif sort_by == "priority":  # high first, then soonest
        query = query.order_by(_PRIORITY_RANK, Todo.due_date.is_(None), Todo.due_date, Todo.id)
    else:
        query = query.order_by(Todo.id)
    return list(db.scalars(query))


def create(db: Session, user_id: int, data: TodoCreate) -> Todo:
    todo = Todo(**data.model_dump(), user_id=user_id)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo


def update(db: Session, todo: Todo, data: TodoUpdate) -> Todo:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(todo, field, value)
    db.commit()
    db.refresh(todo)
    return todo


def delete(db: Session, todo: Todo) -> None:
    db.delete(todo)
    db.commit()


def delete_all_owned(db: Session, user_id: int) -> int:
    """Deletes every todo of this user (and only theirs). Returns how many were removed."""
    result = db.execute(sql_delete(Todo).where(Todo.user_id == user_id))
    db.commit()
    return result.rowcount
