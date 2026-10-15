from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PatchModel(InputModel):
    @model_validator(mode="before")
    @classmethod
    def require_changes(cls, value: Any) -> Any:
        if isinstance(value, dict):
            if not value:
                raise ValueError("Provide at least one field to update")
            if any(item is None for item in value.values()):
                raise ValueError("Update fields cannot be null; omit unchanged fields")
        return value
