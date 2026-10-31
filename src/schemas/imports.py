from typing import Literal
from uuid import UUID

from src.schemas.common import ReadModel


class ProcessingResultRead(ReadModel):
    total_rows: int = 0
    successful_rows: int = 0
    failed_rows: int = 0
    error: str | None = None


class SourceFileRead(ReadModel):
    id: UUID
    supplier_id: int
    filename: str
    status: Literal["uploaded", "processing", "completed", "failed"]
    processing_result: ProcessingResultRead | None = None
