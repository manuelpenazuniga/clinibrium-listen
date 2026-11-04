"""Runtime configuration: Settings read from environment variables (pydantic-settings)."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql://clinibrium:clinibrium@localhost:5432/clinibrium"
    ANTHROPIC_API_KEY: str = ""

    # Track B (ML) — optional. If None, `ml_client.predict()` degrades to
    # None immediately and pipeline A keeps working without B (INV-6).
    ML_PREDICT_URL: str | None = None
    ML_PREDICT_TIMEOUT_S: float = 2.0

    # Audit persistence — best-effort JSONL fallback when Postgres is unavailable.
    AUDIT_LOG_PATH: str = "./audit_events.jsonl"

    # AD-6 / hard rule 2: recording_mode is server-side. It is NEVER taken
    # from the request body — it is set here (env / .env) and passed to the
    # orchestrator. Default False: ambulatory uses Haiku 4.5 (cost); True
    # forces Opus (claude-opus-5-5) for demos / gold-set evaluation.
    RECORDING_MODE: bool = False

    # P1.4: gate for demo-only / debug features (e.g. the "Kill Claude"
    # ?debug_kill_reasoner backdoor). Default False → those features return 403
    # in a normal/public deployment. Enable for the demo or recording.
    DEMO_MODE: bool = False

    # Comma-separated list of browser origins allowed by CORS. The default
    # keeps the local demo working unchanged; a public deploy sets this to
    # the frontend's public URL (e.g. "https://clinibrium.up.railway.app").
    CORS_ORIGINS: str = "http://localhost:3000"

    # Deployment mode (pilot plan §7.1). "demo" (default) = today's behaviour.
    # "study" = the clinical-study deployment: no FHIR bundle in the result
    # (S9), no Kill Claude, and demo/recording switches are refused at
    # startup (fail-closed). Unknown values are a validation error.
    APP_MODE: Literal["demo", "study"] = "demo"

    # Silent mode (plan Q). OFF by default. When True the server never hands
    # the clinical output to the client: /api/evaluate runs the full pipeline
    # and records the AuditEvent but streams only a fixed acknowledgement, and
    # /api/what-would-change returns 403. A client can silence a single case
    # (`?silent=true`) but can never un-silence a server configured silent.
    SILENT_MODE: bool = False

    # Plan T5: usage limits for POST /api/evaluate. None (default) = ON when
    # APP_MODE=demo (a public demo is protected even if the deploy forgets
    # these variables), OFF in study (access control there is authentication).
    RATE_LIMIT_ENABLED: bool | None = None
    RATE_LIMIT_PER_IP_PER_HOUR: int = Field(default=20, ge=1)
    RATE_LIMIT_GLOBAL_PER_DAY: int = Field(default=200, ge=1)
    MAX_CONCURRENT_EVALUATIONS: int = Field(default=4, ge=1)
    RATE_LIMIT_CONCURRENCY_RETRY_S: int = Field(default=30, ge=1)
    # How many trusted proxies append to X-Forwarded-For in front of the
    # backend (Railway's edge: 1). 0 = use the socket peer (local, tests).
    TRUSTED_PROXY_HOPS: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _study_mode_is_closed(self) -> Settings:
        if self.APP_MODE == "study" and (self.DEMO_MODE or self.RECORDING_MODE):
            raise ValueError(
                "APP_MODE=study refuses DEMO_MODE/RECORDING_MODE "
                "(demo and debug features must never reach the study)"
            )
        return self

    @property
    def is_study(self) -> bool:
        return self.APP_MODE == "study"

    @property
    def rate_limit_active(self) -> bool:
        if self.RATE_LIMIT_ENABLED is not None:
            return self.RATE_LIMIT_ENABLED
        return self.APP_MODE == "demo"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
