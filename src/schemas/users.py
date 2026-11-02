from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, EmailStr, StringConstraints

from src.schemas.common import InputModel, PatchModel, ReadModel


def validate_password_length(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must contain at most 72 UTF-8 bytes for bcrypt")
    return value


Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=64)]
Password = Annotated[
    str, StringConstraints(min_length=8, max_length=72), AfterValidator(validate_password_length)
]
NormalizedEmail = Annotated[EmailStr, AfterValidator(lambda value: value.lower())]


class UserCreate(InputModel):
    username: Username
    email: NormalizedEmail
    password: Password


class UserUpdate(PatchModel):
    username: Username | None = None
    email: NormalizedEmail | None = None
    password: Password | None = None
    is_active: bool | None = None


class UserRead(ReadModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime


class LoginRequest(InputModel):
    email: NormalizedEmail
    password: Password


class LoginResponse(ReadModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
