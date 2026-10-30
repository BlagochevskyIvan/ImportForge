import logging
from functools import lru_cache
from typing import Annotated
from uuid import uuid4

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError

from src.api.dependencies import get_current_user
from src.db import config_crud, supplier_crud
from src.db.database import get_session
from src.db.models import SourceFile
from src.schemas.imports import SourceFileRead
from src.schemas.users import UserRead
from src.services.s3_storage import S3Storage

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_FILE_SIZE = 20 * 1024 * 1024


@lru_cache
def get_storage() -> S3Storage:
    try:
        return S3Storage()
    except KeyError as exc:
        raise HTTPException(503, "File storage is not configured") from exc


@router.post("", response_model=SourceFileRead, status_code=201)
async def upload_csv(
    file: UploadFile,
    supplier_id: Annotated[int, Form(gt=0)],
    current_user: Annotated[UserRead, Depends(get_current_user)],
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(415, "Expected a CSV file")
    if len(file.filename) > 255:
        raise HTTPException(422, "Filename is too long")

    size = file.size
    if size is None:
        size = 0
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                break
        await file.seek(0)
    if size > MAX_FILE_SIZE:
        raise HTTPException(413, "File is too large")
    if size == 0:
        raise HTTPException(422, "File is empty")

    file_id = uuid4()
    key = f"raw/{supplier_id}/{file_id}.csv"
    storage = None
    uploaded = False
    async with get_session() as session:
        try:
            async with session.begin():
                supplier = await supplier_crud.get_supplier_by_id(
                    session, supplier_id, user_id=current_user.id
                )
                if supplier is None:
                    raise HTTPException(404, "Supplier not found")
                config = await config_crud.get_config(session, supplier_id, user_id=current_user.id)
                if config is None:
                    raise HTTPException(409, "Save supplier configuration before uploading")
                storage = get_storage()
                await run_in_threadpool(storage.upload, file.file, key)
                uploaded = True
                record = SourceFile(
                    id=file_id,
                    supplier_id=supplier_id,
                    config_data=config.config_data,
                    filename=file.filename,
                    object_key=key,
                    status="uploaded",
                )
                session.add(record)
                await session.flush()
                result = SourceFileRead.model_validate(record)
        except (ClientError, BotoCoreError, S3UploadFailedError) as exc:
            logger.exception("S3 upload failed")
            raise HTTPException(502, "File storage unavailable") from exc
        except SQLAlchemyError as exc:
            logger.exception("Failed to save file metadata: file_id=%s, key=%s", file_id, key)
            if uploaded and storage is not None:
                try:
                    await run_in_threadpool(storage.delete, key)
                except (ClientError, BotoCoreError):
                    logger.exception("S3 cleanup failed")
            raise HTTPException(500, "Failed to save file metadata") from exc
    return result
