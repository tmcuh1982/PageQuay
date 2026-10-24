from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .auth import SCOPES
from .search_options import DDG_REGIONS

ContentFormat = Literal["text", "html", "links", "metadata", "structured"]
ImageMediaType = Literal["image/jpeg", "image/png", "image/webp", "image/gif"]


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


class DownloadImage(Strict):
    url: str = Field(min_length=1, max_length=4096)
    expected_url: str = Field(min_length=1, max_length=4096)
    allow_redirects: bool = True
    max_bytes: int = Field(5_000_000, strict=True, ge=1, le=20_000_000)
    allowed_media_types: list[ImageMediaType] = Field(
        default_factory=lambda: ["image/jpeg", "image/png", "image/webp"],
        min_length=1,
        max_length=4,
        description="Opt-in formats; omission preserves JPEG/PNG/WebP only",
        json_schema_extra={"uniqueItems": True},
    )
    timeout: float = Field(
        120,
        gt=0,
        le=180,
        allow_inf_nan=False,
        description="Total seconds including startup and human waiting",
    )

    @field_validator("allowed_media_types")
    @classmethod
    def unique_media_types(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Duplicate media types")
        return value


class Navigate(Strict):
    url: str = Field(min_length=1, max_length=4096)
    wait_until: Literal["domcontentloaded", "load", "networkidle"] = "domcontentloaded"
    expected_url: str | None = Field(
        None,
        min_length=1,
        max_length=4096,
        description=(
            "Exact final browser URL after challenge resolution; mismatch returns scope_changed. "
            "Enables HTTPS-only navigation."
        ),
    )
    allow_redirects: bool = Field(
        True,
        description=(
            "Defaults to true independently of expected_url and respect_robots. "
            "False rejects a different redirect target before follow."
        ),
    )
    respect_robots: bool = Field(
        False, description="Opt-in bounded robots.txt check; explicit denial blocks acquisition."
    )


class Action(Strict):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    type: Literal[
        "click",
        "fill",
        "select",
        "scroll",
        "wait_for_selector",
        "wait_for_navigation",
        "validate_cookies",
    ]
    selector: str | None = Field(None, max_length=500)
    value: str | None = Field(None, max_length=4096)
    x: int = Field(0, ge=-10000, le=10000)
    y: int = Field(0, ge=-10000, le=10000)
    timeout_ms: int = Field(5000, ge=100, le=10000)

    @model_validator(mode="after")
    def cookie_choice(self):
        if self.type == "validate_cookies" and self.value not in {None, "reject", "accept"}:
            raise ValueError("validate_cookies value must be reject or accept")
        return self


class CookiePolicy(Strict):
    choice: Literal["reject", "accept"] | None = Field(
        None, description="Persistent project choice; null disables automatic cookie clicks."
    )
    timeout_ms: int = Field(1500, ge=100, le=10000)


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
    tab_id: str | None = None
    project: str | None = None
    client_id: str | None = None


class NavigationMetadata(Strict):
    requested_url: str
    final_url: str
    http_status: int | None = Field(
        description="Observed main-document HTTP status; never inferred from DOM"
    )
    http_status_reason: str | None
    content_type: str | None = Field(
        description="Observed main-document Content-Type, distinct from artifact media_type"
    )
    redirect_chain: list[dict[str, Any]]
    redirect_chain_truncated: bool
    observed_at: str = Field(description="ISO 8601 UTC time of main-frame commit")
    navigation_id: str
    source: Literal["browser_main_document_response"]
    main_document_response: dict[str, Any] | None = None
    url_changes: list[dict[str, Any]] = Field(default_factory=list)
    url_changes_truncated: bool = False
    same_document_navigations: list[dict[str, Any]] = Field(default_factory=list)
    same_document_navigations_truncated: bool = False


class NavigationResult(Strict):
    tab_id: str
    url: str
    title: str
    title_truncated: bool
    navigation: NavigationMetadata
    robots: dict[str, Any]
    network_policy: dict[str, Any]
    cookie_consent: dict[str, Any] | None = None


class AcquisitionArtifact(Strict):
    capture_restarts: int = Field(0, ge=0, le=2)
    artifact_id: str
    size: int
    media_type: str
    url: str
    navigation: NavigationMetadata


class DownloadImageResult(Strict):
    artifact_id: str
    url: str = Field(description="Authenticated project-scoped binary artifact endpoint")
    size: int = Field(ge=1, le=20_000_000)
    media_type: ImageMediaType
    sha256: str
    expires_at: float
    requested_url: str
    final_url: str
    redirect_chain: list[dict[str, Any]]
    http_status: Literal[200]
    request_id: str | None
    job_id: str
    tab_id: str
    frame_id: str
    network_request_id: str | None
    original_bytes: Literal[True]


class ContextSelectionDiagnostic(Strict):
    session_type: Literal["unattached", "page", "frame_target", "ancestor_frame_target"]
    path_source: Literal["isolated_frame_owners", "frame_target_root"]
    candidate_count: int = Field(ge=0, le=128)
    stale_candidate_count: int | None = Field(None, ge=0, le=128)
    expected_path: list[int] | None = Field(max_length=32)
    observed_paths: list[list[int] | None] = Field(max_length=8)
    paths_truncated: bool
    failure: Literal["no_candidates", "path_mismatch", "target_root_ambiguous"] | None
    selected_path: list[int] | None = Field(None, max_length=32)


class FrameDiagnostic(Strict):
    cause: Literal[
        "FRAME_DETACHED",
        "TIMEOUT",
        "WORLD_NOT_FOUND",
        "JAVASCRIPT_EXCEPTION",
        "SIZE_LIMIT",
        "SCHEMA_REJECTED",
        "OTHER_ERROR",
    ]
    stage: Literal[
        "visibility",
        "cdp_session",
        "context_selection",
        "isolated_world",
        "extraction",
        "serialization",
        "context_verification",
    ]
    duration_ms: float
    limit_ms: int
    is_detached: bool
    observed_at: str
    interpretation: str
    context_selection: ContextSelectionDiagnostic | None = None


class FrameSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")
    frame_id: str
    parent_frame_id: str | None
    status: Literal["extracted", "omitted", "unavailable"]
    reason: str | None = None
    cause_code: str | None = None
    diagnostic: FrameDiagnostic | None = None
    document: dict[str, Any] | None = None
    context_selection: ContextSelectionDiagnostic | None = None


class StructuredSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: Literal["1.0"]
    source: Literal["rendered_dom"]
    navigation: NavigationMetadata
    captured_at: str
    artifact_id: str
    blocks: list[dict[str, Any]] = Field(
        description="DOM-derived node_id and provenance.xpath; null XPath has an explicit reason"
    )
    frames: list[FrameSnapshot]
    partial: bool
    truncated: bool
    robots: dict[str, Any]
    network_policy: dict[str, Any]


class JobResponse(Strict):
    id: str
    kind: str
    status: Literal["queued", "running", "waiting_for_human", "completed", "failed", "cancelled"]
    created_at: float
    updated_at: float
    result: (
        DownloadImageResult
        | SearchResult
        | NavigationResult
        | AcquisitionArtifact
        | dict[str, Any]
        | None
    )
    error: dict[str, Any] | None
    tab_id: str | None
    project: str
    client_id: str | None
    request_id: str | None


class ErrorResponse(Strict):
    error: dict[str, Any] = Field(
        description="code/message/request_id and optional structured details"
    )
