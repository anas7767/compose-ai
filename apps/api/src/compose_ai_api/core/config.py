from decimal import Decimal
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Compose AI API"
    environment: str = Field(default="local", alias="COMPOSE_ENV")
    api_v1_prefix: str = "/api/v1"
    api_host: str = Field(default="0.0.0.0", alias="COMPOSE_API_HOST")
    api_port: int = Field(default=8000, alias="COMPOSE_API_PORT")
    database_url: str = Field(
        default="postgresql+asyncpg://compose_ai:compose_ai_local_password@localhost:5432/compose_ai",
        alias="DATABASE_URL",
    )
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    clerk_secret_key: str | None = Field(default=None, alias="CLERK_SECRET_KEY")
    clerk_jwks_url: str | None = Field(default=None, alias="CLERK_JWKS_URL")
    clerk_issuer: str | None = Field(default=None, alias="CLERK_ISSUER")
    clerk_authorized_parties: list[str] = Field(
        default_factory=list,
        alias="CLERK_AUTHORIZED_PARTIES",
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        alias="CORS_ORIGINS",
    )
    ai_provider: str = Field(default="mock", alias="AI_PROVIDER")
    ai_fallback_provider: str | None = Field(default=None, alias="AI_FALLBACK_PROVIDER")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_text_model: str | None = Field(default="gemini-3.5-flash", alias="GEMINI_TEXT_MODEL")
    gemini_image_model: str | None = Field(
        default="gemini-3.1-flash-image", alias="GEMINI_IMAGE_MODEL"
    )
    exterior_design_image_model: str | None = Field(
        default=None, alias="EXTERIOR_DESIGN_IMAGE_MODEL"
    )
    asset_storage_provider: str = Field(default="local", alias="ASSET_STORAGE_PROVIDER")
    asset_storage_local_root: str | None = Field(
        default=".compose-assets", alias="ASSET_STORAGE_LOCAL_ROOT"
    )
    asset_public_base_url: str | None = Field(
        default="/api/v1/assets", alias="ASSET_PUBLIC_BASE_URL"
    )
    asset_storage_prefix: str = Field(default="compose-ai", alias="ASSET_STORAGE_PREFIX")
    asset_storage_s3_bucket: str | None = Field(default=None, alias="ASSET_STORAGE_S3_BUCKET")
    asset_storage_s3_region: str = Field(default="us-east-1", alias="ASSET_STORAGE_S3_REGION")
    asset_storage_s3_endpoint_url: str | None = Field(
        default=None, alias="ASSET_STORAGE_S3_ENDPOINT_URL"
    )
    asset_storage_s3_access_key_id: str | None = Field(
        default=None, alias="ASSET_STORAGE_S3_ACCESS_KEY_ID"
    )
    asset_storage_s3_secret_access_key: str | None = Field(
        default=None, alias="ASSET_STORAGE_S3_SECRET_ACCESS_KEY"
    )
    asset_storage_s3_public_base_url: str | None = Field(
        default=None, alias="ASSET_STORAGE_S3_PUBLIC_BASE_URL"
    )
    asset_max_image_bytes: int = Field(
        default=10_485_760, ge=1_000, le=50_000_000, alias="ASSET_MAX_IMAGE_BYTES"
    )
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_organization: str | None = Field(default=None, alias="OPENAI_ORGANIZATION")
    openai_project: str | None = Field(default=None, alias="OPENAI_PROJECT")
    openai_model_brief: str | None = Field(default=None, alias="OPENAI_MODEL_BRIEF")
    openai_model_chat: str | None = Field(default=None, alias="OPENAI_MODEL_CHAT")
    openai_model_normalizer: str | None = Field(default=None, alias="OPENAI_MODEL_NORMALIZER")
    openai_model_floor_plan: str | None = Field(default=None, alias="OPENAI_MODEL_FLOOR_PLAN")
    openai_model_fallback: str | None = Field(default=None, alias="OPENAI_MODEL_FALLBACK")
    ai_prompt_environment: str = Field(default="development", alias="AI_PROMPT_ENV")
    ai_request_timeout_seconds: float = Field(
        default=45.0, gt=0, le=300, alias="AI_REQUEST_TIMEOUT_SECONDS"
    )
    ai_max_retries: int = Field(default=2, ge=0, le=5, alias="AI_MAX_RETRIES")
    ai_max_input_tokens: int = Field(default=32_000, ge=1_000, alias="AI_MAX_INPUT_TOKENS")
    ai_max_output_tokens: int = Field(default=4_000, ge=256, alias="AI_MAX_OUTPUT_TOKENS")
    ai_max_concurrent_runs_per_org: int = Field(
        default=4, ge=1, le=100, alias="AI_MAX_CONCURRENT_RUNS_PER_ORG"
    )
    ai_user_rate_limit_per_minute: int = Field(
        default=10, ge=1, le=1_000, alias="AI_USER_RATE_LIMIT_PER_MINUTE"
    )
    ai_org_daily_cost_limit_usd: Decimal = Field(
        default=Decimal("5.00"), ge=0, alias="AI_ORG_DAILY_COST_LIMIT_USD"
    )
    ai_org_monthly_cost_limit_usd: Decimal = Field(
        default=Decimal("50.00"), ge=0, alias="AI_ORG_MONTHLY_COST_LIMIT_USD"
    )
    ai_input_price_per_1m_usd: Decimal = Field(
        default=Decimal("0"), ge=0, alias="AI_INPUT_PRICE_PER_1M_USD"
    )
    ai_output_price_per_1m_usd: Decimal = Field(
        default=Decimal("0"), ge=0, alias="AI_OUTPUT_PRICE_PER_1M_USD"
    )
    ai_cache_ttl_seconds: int = Field(
        default=86_400, ge=60, le=2_592_000, alias="AI_CACHE_TTL_SECONDS"
    )
    ai_provider_failure_threshold: int = Field(
        default=3, ge=1, le=20, alias="AI_PROVIDER_FAILURE_THRESHOLD"
    )
    ai_provider_degraded_seconds: int = Field(
        default=120, ge=10, le=3_600, alias="AI_PROVIDER_DEGRADED_SECONDS"
    )
    ai_run_retention_days: int = Field(default=90, ge=1, le=2_555, alias="AI_RUN_RETENTION_DAYS")
    ai_mock_seed: str = Field(default="compose-ai", alias="AI_MOCK_SEED")
    floor_plan_max_concurrent_runs_per_org: int = Field(
        default=2, ge=1, le=20, alias="FLOOR_PLAN_MAX_CONCURRENT_RUNS_PER_ORG"
    )
    floor_plan_max_solver_attempts: int = Field(
        default=20, ge=1, le=100, alias="FLOOR_PLAN_MAX_SOLVER_ATTEMPTS"
    )
    floor_plan_max_provider_retries: int = Field(
        default=2, ge=0, le=10, alias="FLOOR_PLAN_MAX_PROVIDER_RETRIES"
    )
    floor_plan_max_processing_seconds: int = Field(
        default=180, ge=10, le=1800, alias="FLOOR_PLAN_MAX_PROCESSING_SECONDS"
    )
    floor_plan_max_invalid_candidates: int = Field(
        default=12, ge=1, le=100, alias="FLOOR_PLAN_MAX_INVALID_CANDIDATES"
    )
    floor_plan_diversity_threshold: Decimal = Field(
        default=Decimal("0.250"), ge=0, le=1, alias="FLOOR_PLAN_DIVERSITY_THRESHOLD"
    )
    worker_heartbeat_interval_seconds: int = Field(
        default=10, ge=1, le=300, alias="WORKER_HEARTBEAT_INTERVAL_SECONDS"
    )
    worker_heartbeat_stale_seconds: int = Field(
        default=45, ge=5, le=3_600, alias="WORKER_HEARTBEAT_STALE_SECONDS"
    )
    readiness_ai_provider_check_enabled: bool = Field(
        default=True, alias="READINESS_AI_PROVIDER_CHECK_ENABLED"
    )
    readiness_ai_provider_timeout_seconds: float = Field(
        default=5.0, gt=0, le=30, alias="READINESS_AI_PROVIDER_TIMEOUT_SECONDS"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]

        return value

    @field_validator("clerk_authorized_parties", mode="before")
    @classmethod
    def parse_clerk_authorized_parties(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [party.strip() for party in value.split(",") if party.strip()]

        return value

    @field_validator(
        "clerk_jwks_url",
        "clerk_issuer",
        "ai_fallback_provider",
        "gemini_api_key",
        "gemini_text_model",
        "gemini_image_model",
        "exterior_design_image_model",
        "asset_storage_local_root",
        "asset_public_base_url",
        "asset_storage_s3_bucket",
        "asset_storage_s3_endpoint_url",
        "asset_storage_s3_access_key_id",
        "asset_storage_s3_secret_access_key",
        "asset_storage_s3_public_base_url",
        "openai_api_key",
        "openai_organization",
        "openai_project",
        "openai_model_brief",
        "openai_model_chat",
        "openai_model_normalizer",
        "openai_model_floor_plan",
        "openai_model_fallback",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: str | None) -> str | None:
        if value == "":
            return None

        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_runtime_settings(settings: Settings) -> None:
    if settings.ai_provider == "gemini" and not settings.gemini_api_key:
        raise RuntimeError("Gemini API key missing")
    if settings.environment != "local" and settings.ai_provider == "mock":
        raise RuntimeError("AI_PROVIDER must be explicitly configured outside local development.")
