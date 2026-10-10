from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .auth import SCOPES
from .search_options import DDG_REGIONS

ContentFormat = Literal["text", "html", "links", "metadata", "structured"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProjectCreate(Strict):
    slug: str = Field(min_length=2, max_length=48, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=100)


class KeyCreate(Strict):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["search:read", "content:read"])
    expires_at: float | None = Field(default=None, allow_inf_nan=False)
    rate_limit: int = Field(60, ge=1, le=600)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value):
        if not value or not set(value) <= SCOPES:
            raise ValueError("Invalid scopes")
        return value


class KeyUpdate(KeyCreate):
    scopes: list[str]
    expires_at: float | None = Field(allow_inf_nan=False)
    rate_limit: int = Field(ge=1, le=600)


class KeyInfoProject(Strict):
    slug: str
    name: str


class KeyInfoRateLimit(Strict):
    configured_requests_per_minute: int
    project_requests_per_minute: int
    effective_requests_per_minute: int
    window_seconds: Literal[60]
    remaining_requests: int = Field(ge=0)
    resets_at: float = Field(description="Unix timestamp in seconds (UTC)")


class KeyInfo(Strict):
    key_id: str
    name: str
    prefix: str
    project: KeyInfoProject
    scopes: list[str]
    expires_at: float | None = Field(
        description="Unix timestamp in seconds (UTC); null means never"
    )
    rate_limit: KeyInfoRateLimit


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
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "robot agriculture",
                    "engine": "duckduckgo",
                    "limit": 10,
                    "locale": "fr-FR",
                },
                {
                    "query": "robot agriculture",
                    "engine": "duckduckgo",
                    "limit": 10,
                    "locale": "fr-FR",
                    "cursor": "A" * 43,
                },
                {
                    "query": "robot agriculture",
                    "engine": "duckduckgo",
                    "region": "fr-fr",
                    "time_range": "week",
                    "limit": 10,
                },
            ]
        }
    )
    engine: Literal["auto", "duckduckgo", "google", "brave"] | None = None
    strategy: Literal["fallback", "merge"] | None = None
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(10, ge=1, le=50)
    locale: str = Field("fr-FR", pattern=r"^[a-z]{2}-[A-Z]{2}$")
    region: str | None = Field(
        None,
        description="DuckDuckGo region (country/language); overrides locale's region. "
        "Use wt-wt for all regions. Requires the DuckDuckGo engine.",
        json_schema_extra={"enum": [*DDG_REGIONS, None]},
    )
    time_range: Literal["any", "day", "week", "month", "year"] = Field(
        "any",
        description="DuckDuckGo date filter; any means all dates. "
        "A recent result does not guarantee a recent event.",
    )
    cursor: str | None = Field(
        None,
        min_length=43,
        max_length=43,
        pattern=r"^[A-Za-z0-9_-]{43}$",
        description="Opaque DuckDuckGo continuation; keep query, engine, locale, "
        "region and time_range unchanged.",
    )

    @field_validator("region")
    @classmethod
    def supported_region(cls, value):
        if value is not None and value not in DDG_REGIONS:
            raise ValueError("Unsupported DuckDuckGo region")
        return value


class SearchHit(Strict):
    rank: int
    engine_rank: int
    page_number: int | None = None
    title: str
    url: str = Field(description="Legacy normalized URL, retained for compatibility")
    exact_url: str = Field(description="Exact target URL after unwrapping the engine redirect")
    snippet: str
    source_engines: list[str]
    fetched_at: float
    result_type: str


class SearchResult(Strict):
    project: str
    query: str
    locale: str
    region: str | None = Field(description="Requested region override, or null to use locale")
    time_range: Literal["any", "day", "week", "month", "year"]
    results: list[SearchHit]
    engine_errors: list[dict[str, Any]]
    engine: str
    engines_used: list[str]
    requested_count: int
    effective_limit: int
    returned_count: int
    next_cursor: str | None
    has_more: bool | None = Field(description="null means no usable continuation or unknown end")
    stop_reason: str | None
    partial: bool
    pages_fetched: int
    duplicates_discarded: int
    cursor_expires_at: float | None


class SearchAccepted(Strict):
    job_id: str
    status: Literal["queued", "running", "waiting_for_human", "completed", "failed", "cancelled"]
    url: str
    idempotency_replayed: bool = False


class JobResponse(Strict):
    id: str
    kind: str
    status: Literal["queued", "running", "waiting_for_human", "completed", "failed", "cancelled"]
    created_at: float
    updated_at: float
    result: SearchResult | dict[str, Any] | None
    error: dict[str, Any] | None
    tab_id: str | None


class ErrorResponse(Strict):
    error: dict[str, Any] = Field(
        description="code/message/request_id and optional structured details"
    )
