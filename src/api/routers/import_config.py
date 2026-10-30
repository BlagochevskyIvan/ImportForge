from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_current_user
from src.db import config_crud, supplier_crud
from src.db.database import get_session
from src.schemas.import_config import ImportConfigRead, ImportConfigUpdate
from src.schemas.users import UserRead

router = APIRouter()

# None -> configure for the first time
@router.get("/{supplier_id}/config", response_model=ImportConfigRead | None)
async def get_supplier_config(
    supplier_id: int,
    current_user: Annotated[UserRead, Depends(get_current_user)],
):
    async with get_session() as session:
        supplier = await supplier_crud.get_supplier_by_id(
            session, supplier_id, user_id=current_user.id
        )
        if supplier is None:
            raise HTTPException(404, "Supplier not found")
        config = await config_crud.get_config(session, supplier_id, user_id=current_user.id)
        return ImportConfigRead.model_validate(config) if config is not None else None


@router.put("/{supplier_id}/config", response_model=ImportConfigRead)
async def save_supplier_config(
    supplier_id: int,
    data: ImportConfigUpdate,
    current_user: Annotated[UserRead, Depends(get_current_user)],
):
    async with get_session() as session, session.begin():
        config = await config_crud.save_config(
            session, supplier_id, data.config_data, user_id=current_user.id
        )
        if config is None:
            raise HTTPException(404, "Supplier not found")
        result = ImportConfigRead.model_validate(config)
    return result
