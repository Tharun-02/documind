from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ────────────────────────────────────
    APP_NAME: str = "DocuMind"
    DEBUG: bool = False

    # ── Database ───────────────────────────────
    DATABASE_URL: str

    # ── Redis ──────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT Auth ───────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── OpenAI ─────────────────────────────────
    OPENAI_API_KEY: str = ""

    # ── Pinecone ───────────────────────────────
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "documind"
    PINECONE_ENVIRONMENT: str = "us-east-1-aws"

    # ── LangSmith ──────────────────────────────
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_PROJECT: str = "documind"

    # ── File Storage ───────────────────────────
    UPLOAD_DIR: str = "./uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
