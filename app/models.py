"""Validated authentication request models."""
from pydantic import BaseModel, Field, SecretStr, field_validator


class UsernameMixin(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=40,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
        description="3-40 letters, digits, dots, underscores or hyphens.",
    )

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LoginRequest(UsernameMixin):
    password: SecretStr = Field(min_length=8, max_length=128)


class RegisterRequest(UsernameMixin):
    password: SecretStr = Field(
        min_length=8,
        max_length=128,
        description="Use at least 8 characters.",
    )
