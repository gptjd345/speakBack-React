from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    DATABASE_URL: str
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    JWT_SECRET_KEY: str  # .env에서 관리
    JWT_ALGORITHM: str   # .env에서 관리

    # Pydantic v2 style
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
