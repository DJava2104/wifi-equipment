from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    MINIO_ENDPOINT: str = "localhost"
    MINIO_PORT: int = 9000
    MINIO_ACCESS_KEY: str = "root"
    MINIO_SECRET_KEY: str = "rootpassword"
    MINIO_BUCKET: str = "wifi-routers"
    MINIO_USE_SSL: bool = False

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def MINIO_URL(self) -> str:
        scheme = "https" if self.MINIO_USE_SSL else "http"
        return f"{scheme}://{self.MINIO_ENDPOINT}:{self.MINIO_PORT}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()