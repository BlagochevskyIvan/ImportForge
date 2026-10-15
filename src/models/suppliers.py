from typing import Annotated

from pydantic import EmailStr, StringConstraints

from src.models.common import InputModel, PatchModel, ReadModel

SupplierName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class SupplierCreate(InputModel):
    name: SupplierName
    contact_email: EmailStr


class SupplierUpdate(PatchModel):
    name: SupplierName | None = None
    contact_email: EmailStr | None = None
    is_active: bool | None = None


class SupplierRead(ReadModel):
    id: int
    user_id: int
    name: str
    contact_email: EmailStr
    is_active: bool
