from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.auth.dependencies import get_current_user
from src.db import supplier_crud
from src.db.database import get_session
from src.models.suppliers import SupplierCreate, SupplierRead, SupplierUpdate
from src.models.user import UserRead

router = APIRouter()


@router.post("", response_model=SupplierRead, status_code=201)
async def create_supplier(
    data: SupplierCreate,
    current_user: Annotated[UserRead, Depends(get_current_user)],
):
    async with get_session() as session, session.begin():
        supplier = await supplier_crud.create_supplier(session, data, user_id=current_user.id)
        result = SupplierRead.model_validate(supplier)
    return result


@router.get("", response_model=list[SupplierRead])
async def get_suppliers(
    current_user: Annotated[UserRead, Depends(get_current_user)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    async with get_session() as session:
        suppliers = await supplier_crud.list_suppliers(
            session, user_id=current_user.id, offset=offset, limit=limit
        )
        return [SupplierRead.model_validate(supplier) for supplier in suppliers]


@router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(
    supplier_id: int,
    current_user: Annotated[UserRead, Depends(get_current_user)],
):
    async with get_session() as session:
        supplier = await supplier_crud.get_supplier_by_id(
            session,
            supplier_id,
            user_id=current_user.id,
        )

        if supplier is None:
            raise HTTPException(404, "Supplier not found")

        return SupplierRead.model_validate(supplier)


@router.patch("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    current_user: Annotated[UserRead, Depends(get_current_user)],
):
    async with get_session() as session, session.begin():
        supplier = await supplier_crud.update_supplier(
            session, supplier_id, data, user_id=current_user.id
        )
        if supplier is None:
            raise HTTPException(404, "Supplier not found")
        result = SupplierRead.model_validate(supplier)
    return result


@router.post("/suppliers/{id}/config")
async def create_supplier_config(id: int):
    pass


@router.get("/suppliers/{id}/config")
async def get_supplier_config(id: int):
    pass
