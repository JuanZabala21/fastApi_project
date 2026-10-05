from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbDep
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


def _get_user_or_404(db: DbDep, user_id: int) -> User:
    user = user_service.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"User {user_id} not found")
    return user


def _ensure_self(current_user: User, user_id: int) -> None:
    if current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only modify your own user")


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: DbDep):
    """Public: anyone can sign up."""
    if user_service.get_by_email(db, data.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return user_service.create(db, data)


@router.get("", response_model=list[UserRead])
def list_users(
    db: DbDep,
    _: CurrentUser,  # requires a valid token; the value itself isn't used
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
):
    return user_service.list_users(db, skip, limit)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: DbDep, _: CurrentUser):
    return _get_user_or_404(db, user_id)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, data: UserUpdate, db: DbDep, current_user: CurrentUser):
    _ensure_self(current_user, user_id)
    if data.email and data.email != current_user.email and user_service.get_by_email(db, data.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return user_service.update(db, current_user, data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: DbDep, current_user: CurrentUser):
    _ensure_self(current_user, user_id)
    user_service.delete(db, current_user)
