from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .auth import SCOPES

ContentFormat = Literal["text", "html", "links", "metadata", "structured"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProjectCreate(Strict):
    slug: str = Field(min_length=2, max_length=48, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=100)


class KeyCreate(Strict):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["search:read", "content:read"])
    expires_at: float | None = None
    rate_limit: int = Field(60, ge=1, le=600)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value):
        if not value or not set(value) <= SCOPES:
            raise ValueError("Invalid scopes")
        return value


class Navigate(Strict):
    url: str = Field(min_length=1, max_length=4096)
    wait_until: Literal["domcontentloaded", "load", "networkidle"] = "domcontentloaded"


class Action(Strict):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    type: Literal["click", "fill", "select", "scroll", "wait_for_selector", "wait_for_navigation"]
    selector: str | None = Field(None, max_length=500)
    value: str | None = Field(None, max_length=4096)
    x: int = Field(0, ge=-10000, le=10000)
    y: int = Field(0, ge=-10000, le=10000)
    timeout_ms: int = Field(5000, ge=100, le=10000)


class Actions(Strict):
    actions: list[Action] = Field(min_length=1, max_length=20)


class Search(Strict):
    engine: Literal["auto", "duckduckgo", "google", "brave"] | None = None
    strategy: Literal["fallback", "merge"] | None = None
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(10, ge=1, le=50)
    locale: str = Field("fr-FR", pattern=r"^[a-z]{2}-[A-Z]{2}$")
