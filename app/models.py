"""Validated request models."""
from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=40,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
        description="Demo username: 3-40 letters, digits, dots, underscores or hyphens.",
    )

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value
