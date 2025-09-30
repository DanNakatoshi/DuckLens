from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Polygon.io API (Required)
    polygon_api_key: str

    # Supabase (Optional for now)
    supabase_url: str | None = None
    supabase_key: str | None = None

    # Reddit API (Optional for now)
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "DuckLens/0.1.0"

    # Twitter API (Optional)
    twitter_api_key: str | None = None
    twitter_api_secret: str | None = None
    twitter_bearer_token: str | None = None

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2"

    # Database
    duckdb_path: str = "./data/ducklens.db"

    # Application
    app_env: str = "development"
    log_level: str = "INFO"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True


def get_settings() -> Settings:
    """Get settings instance (for dependency injection)."""
    return Settings()  # type: ignore[call-arg]


# Global settings instance
settings = get_settings()
