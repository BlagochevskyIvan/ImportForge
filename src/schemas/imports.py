from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from src.schemas.common import InputModel, ReadModel

RunStatus = Literal["queued", "processing", "retry_wait", "completed", "failed"]


class ProcessingResultRead(ReadModel):
    total_rows: int = 0
    successful_rows: int = 0
    failed_rows: int = 0
    error: str | None = None


class ImportRunCreate(InputModel):
    config_id: Annotated[int, Field(gt=0)] | None = None


class ImportRunRead(ReadModel):
    id: UUID
    source_file_id: UUID
    config_id: int | None
    config_name: str
    config_data: dict
    status: RunStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    attempt_count: int
    next_retry_at: datetime | None
    error_code: str | None
    error_message: str | None
    processing_result: ProcessingResultRead | None


class SourceFileRead(ReadModel):
    id: UUID
    supplier_id: int
    filename: str
    status: Literal["uploaded", "queued", "processing", "retry_wait", "completed", "failed"]
    processing_result: ProcessingResultRead | None = None
    latest_run: ImportRunRead | None = None

    @classmethod
    def from_file(cls, source_file, run=None):
        metadata = None
        if run is not None:
            stored = run.processing_result
            if isinstance(stored, ProcessingResultRead):
                stored = stored.model_dump()
            metadata = {**(stored or {}), "error": run.error_message}
        return cls(
            id=source_file.id,
            supplier_id=source_file.supplier_id,
            filename=source_file.filename,
            status=run.status if run is not None else "uploaded",
            processing_result=metadata,
            latest_run=ImportRunRead.model_validate(run) if run is not None else None,
        )
