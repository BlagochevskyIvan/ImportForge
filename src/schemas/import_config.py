from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from src.schemas.common import InputModel, ReadModel

ColumnName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\x00]+$"),
]
ConfigName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False)]


class CsvColumn(InputModel):
    source: ColumnName
    target: ColumnName
    type: Literal["text", "integer", "decimal"] = "text"
    required: bool = False
    trim: bool = True
    min_value: FiniteDecimal | None = None
    max_value: FiniteDecimal | None = None

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.type == "text" and (self.min_value is not None or self.max_value is not None):
            raise ValueError("Numeric bounds require an integer or decimal column")
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError("min_value must not exceed max_value")
        return self


def upgrade_legacy_mapping(value: dict) -> dict:
    """Read old snapshots without changing their original three-field semantics."""
    mapping = value.get("column_mapping")
    if not isinstance(mapping, dict) or not all(isinstance(item, str) for item in mapping.values()):
        raise ValueError("column_mapping must map source names to target names")
    sources = [key.strip() if isinstance(key, str) else key for key in mapping]
    if len(sources) != len(set(sources)):
        raise ValueError("Source column names must be unique after trimming")
    legacy = len(mapping) == 3 and set(mapping.values()) == {"sku", "name", "price"}
    entries = list(mapping.items())
    if legacy:
        entries.sort(key=lambda item: ["sku", "name", "price"].index(item[1]))
    columns = []
    for source, target in entries:
        column = {"source": source, "target": target}
        if legacy:
            column["required"] = True
            if target == "price":
                column.update(type="decimal", min_value=0)
        columns.append(column)
    return {
        **{key: item for key, item in value.items() if key != "column_mapping"},
        "columns": columns,
    }


class CsvConfig(InputModel):
    """Ordered output columns and per-column rules; no globally required fields."""

    schema_version: Literal[2] = 2
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    encoding: Literal["utf-8", "utf-8-sig", "cp1251"] = "utf-8"
    columns: list[CsvColumn] = Field(min_length=1, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def read_legacy_snapshot(cls, value: Any) -> Any:
        if isinstance(value, dict) and "column_mapping" in value:
            if "columns" in value:
                raise ValueError("Use columns or legacy column_mapping, not both")
            return upgrade_legacy_mapping(value)
        return value

    @field_validator("delimiter")
    @classmethod
    def validate_delimiter(cls, value: str) -> str:
        if value in {chr(10), chr(13), chr(0), '"'}:
            raise ValueError("Delimiter cannot be a newline, NUL or quote")
        return value

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, value: list[CsvColumn]) -> list[CsvColumn]:
        targets = [column.target for column in value]
        if len(targets) != len(set(targets)):
            raise ValueError("Output column names must be unique")
        return value


class ImportConfigCreate(InputModel):
    name: ConfigName = "Основная"
    config_data: CsvConfig


class ImportConfigUpdate(ImportConfigCreate):
    """Append an immutable version of the named configuration when it changes."""


class ImportConfigRead(ReadModel):
    id: int
    supplier_id: int
    name: str = "Основная"
    config_data: CsvConfig
