from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Semiconductor Equipment Management System"
    SECRET_KEY: str = "change-me-in-production-please-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:8080"]

    SQLALCHEMY_DATABASE_URI: str = "sqlite:///./data/app.db"

    # 服务运行参数（由系统设置界面维护，写入 .env 文件后由 pydantic-settings 自动加载）
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
