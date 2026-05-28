"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Runtime configuration.

    Defaults are tuned for local development against the SQLite DB and the
    deterministic mock LLM provider, so the eval suite runs offline.

    Instantiate directly (``Settings()``) at the composition root and
    thread the instance through the container — there is no global
    accessor on purpose.
    """

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str | None = Field(default=None)
    llm_provider: str = Field(default="mock", description="'mock' or 'gemini'")
    gemini_model: str = Field(default="gemini-2.0-flash-exp")

    database_url: str = Field(default="sqlite+aiosqlite:///./claims.db")

    policy_terms_path: str = Field(default=str(REPO_ROOT / "policy_terms.json"))
    policy_rules_path: str = Field(default=str(REPO_ROOT / "policy_rules.json"))
    test_cases_path: str = Field(default=str(REPO_ROOT / "test_cases.json"))

    log_level: str = Field(default="INFO")
    cors_origins: str = Field(default="http://localhost:3000")
    cors_origin_regex: str | None = Field(
        default=None,
        description=(
            "Optional regex allowed by CORSMiddleware.allow_origin_regex. "
            "Useful for Vercel preview URLs, e.g. "
            "r'^https://your-app(-[a-z0-9-]+)?\\.vercel\\.app$'."
        ),
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
