from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbDep, TodoUser
from app.models.todo import Todo as TodoModel
from app.schemas.todo import Priority, Todo, TodoCreate, TodoUpdate
from app.services import todo_service

router = APIRouter(prefix="/todos", tags=["todos"])


def _get_todo_or_404(db: DbDep, user: TodoUser, todo_id: int) -> TodoModel:
    # 404 (not 403) when it belongs to someone else: don't reveal that the id exists
    todo = todo_service.get_owned(db, todo_id, user.id)
    if todo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Todo {todo_id} not found")
    return todo


@router.get("", response_model=list[Todo])
def list_todos(
    db: DbDep,
    user: TodoUser,
    done: bool | None = None,  # optional query param: /todos?done=true
    limit: Annotated[int, Query(ge=1, le=100)] = 10,  # validated query param
    priority: Priority | None = None,
    due_from: date | None = None,  # due_date >= this day
    due_to: date | None = None,  # due_date <= this day
    overdue: bool = False,  # past due and not done
    has_due_date: bool | None = None,  # true = scheduled, false = no day assigned
    sort_by: todo_service.SortBy = "id",
):
    return todo_service.list_owned(
        db, user.id, done, limit, priority, due_from, due_to, overdue, has_due_date, sort_by
    )


@router.post("", response_model=Todo, status_code=status.HTTP_201_CREATED)
def create_todo(data: TodoCreate, db: DbDep, user: TodoUser):  # body parsed from JSON
    return todo_service.create(db, user.id, data)


@router.delete("")
def delete_all_todos(db: DbDep, user: CurrentUser, confirm: bool = False):
    """Deletes ALL of the user's todos. Needs ?confirm=true so it can't happen by accident, and a full
    token: the restricted "todos" tokens (MCP) can delete one todo at a time but not wipe everything."""
    if not confirm:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add ?confirm=true to delete all your todos")
    return {"deleted": todo_service.delete_all_owned(db, user.id)}


@router.get("/{todo_id}", response_model=Todo)  # path parameter
def get_todo(todo_id: int, db: DbDep, user: TodoUser):
    return _get_todo_or_404(db, user, todo_id)


@router.patch("/{todo_id}", response_model=Todo)
def update_todo(todo_id: int, data: TodoUpdate, db: DbDep, user: TodoUser):
    return todo_service.update(db, _get_todo_or_404(db, user, todo_id), data)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int, db: DbDep, user: TodoUser):
    todo_service.delete(db, _get_todo_or_404(db, user, todo_id))
