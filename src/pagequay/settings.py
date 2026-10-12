from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search_default_engine: Literal["duckduckgo", "brave", "google", "auto"] = "auto"
    search_auto_strategy: Literal["fallback", "merge"] = "fallback"
    search_max_results: int = Field(10, ge=1, le=50)
    search_max_pages: int = Field(10, ge=1, le=30)
    search_max_total_results: int = Field(200, ge=1, le=1000)
    search_cursor_ttl_minutes: int = Field(15, ge=1, le=60)
    search_max_cursors_per_project: int = Field(100, ge=1, le=1000)
    max_tabs_per_project: int = Field(8, ge=1, le=30)
    max_concurrent_browsers: int = Field(3, ge=1, le=10)
    max_concurrent_jobs: int = Field(4, ge=1, le=20)
    max_queued_jobs: int = Field(30, ge=1, le=200)
    max_artifact_bytes_per_project: int = Field(100_000_000, ge=1_000_000, le=2_000_000_000)
    per_key_rate_limit: int = Field(60, ge=1, le=600)
    navigation_timeout_seconds: int = Field(30, ge=1, le=120)
    headless: bool = False
    browser_start_minimized: bool = False
    browser_start_on_demand: bool = True
    browser_idle_timeout_minutes: int = Field(30, ge=1, le=1440)
    content_cache_ttl_minutes: int = Field(60, ge=1, le=10080)
    soft_restart_after_hours: int | None = Field(None, ge=1, le=168)
    audit_log_retention_days: int = Field(30, ge=1, le=365)
    artifact_retention_hours: int = Field(24, ge=1, le=168)
    allowed_domains: list[str] = Field(default_factory=list, max_length=100)
    blocked_domains: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("allowed_domains", "blocked_domains")
    @classmethod
    def domains(cls, values):
        import re

        result = []
        for value in values:
            value = value.lower().strip().rstrip(".")
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", value):
                raise ValueError("Use exact domain names, without scheme, port or wildcards")
            result.append(value)
        return result


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PQ_", env_file=".env", extra="ignore")
    data_dir: Path = Path.home() / "Library/Application Support/PageQuay"
    port: int = Field(8765, ge=1024, le=65535)
    api_port: int = Field(8766, ge=1024, le=65535)
    allowed_hosts: list[str] = ["127.0.0.1", "localhost"]
    allowed_origins: list[str] = ["http://127.0.0.1:8765", "http://localhost:8765"]
    secure_cookies: bool = False
    development: bool = False
    browser_channel: Literal["chromium", "chrome"] = "chromium"
    session_absolute_hours: int = 12
    session_idle_minutes: int = 30
    max_payload_bytes: int = 65536
    max_content_bytes: int = 2_000_000
    job_timeout_seconds: int = 180
    human_timeout_seconds: int = 600
    websocket_lifetime_seconds: int = 600
    audit_queue_size: int = Field(512, ge=16, le=4096)
    audit_events_per_minute: int = Field(2400, ge=60, le=10000)
    audit_events_per_project_minute: int = Field(600, ge=30, le=5000)
    audit_max_rows: int = Field(20000, ge=100, le=100000)
    audit_max_bytes: int = Field(64_000_000, ge=1_000_000, le=256_000_000)
    policy: Policy = Field(default_factory=Policy)

    @model_validator(mode="after")
    def separate_listener_ports(self):
        if self.api_port == self.port:
            raise ValueError("Administration and API listeners require distinct ports")
        return self

    @field_validator("allowed_hosts", "allowed_origins")
    @classmethod
    def no_wildcard(cls, values):
        if not values or any("*" in value for value in values):
            raise ValueError("Explicit hosts/origins required")
        return values
