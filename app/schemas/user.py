from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)


class UserRead(BaseModel):
    """What the API returns. Note: no password / hash field, so it can never leak."""

    model_config = ConfigDict(from_attributes=True)  # allows building it from an ORM object

    id: int
    email: EmailStr
    full_name: str | None
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
