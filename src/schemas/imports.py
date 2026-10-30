from typing import Literal
from uuid import UUID

from src.schemas.common import ReadModel


class SourceFileRead(ReadModel):
    id: UUID
    supplier_id: int
    filename: str
    status: Literal["uploaded"]
