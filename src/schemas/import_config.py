from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator

from src.schemas.common import InputModel, ReadModel

SourceColumn = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
TargetColumn = Literal["sku", "name", "price"]


class CsvConfig(InputModel):
    """CSV with a header row; source column names map to ImportForge fields."""

    delimiter: str = Field(default=",", min_length=1, max_length=1)
    encoding: Literal["utf-8", "utf-8-sig", "cp1251"] = "utf-8"
    column_mapping: dict[SourceColumn, TargetColumn] = Field(min_length=3, max_length=3)

    @field_validator("delimiter")
    @classmethod
    def validate_delimiter(cls, value: str) -> str:
        if value in {chr(10), chr(13), chr(0), '"'}:
            raise ValueError("Delimiter cannot be a newline, NUL or quote")
        return value

    @field_validator("column_mapping")
    @classmethod
    def validate_mapping(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) != 3 or set(value.values()) != {"sku", "name", "price"}:
            raise ValueError("Map sku, name and price exactly once each")
        return value


class ImportConfigCreate(InputModel):
    config_data: CsvConfig


class ImportConfigUpdate(InputModel):
    """Full replacement of config_data, not a partial nested JSON update."""

    config_data: CsvConfig


class ImportConfigRead(ReadModel):
    id: int
    supplier_id: int
    config_data: CsvConfig
