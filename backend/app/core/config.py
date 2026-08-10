from pydantic_settings import BaseSettings
from typing import List, Optional
import secrets
import os


def _backend_root_dir() -> str:
    """返回 backend/ 项目根目录的绝对路径（不受进程启动 CWD 影响）。"""
    # __file__ = backend/app/core/config.py → 上三级 = backend/
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, os.pardir, os.pardir, os.pardir))


BACKEND_ROOT: str = _backend_root_dir()
DATA_DIR: str = os.path.join(BACKEND_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Semiconductor Equipment Management System"
    SECRET_KEY: str = "change-me-in-production-please-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    # 访问令牌 2 小时；刷新令牌 7 天
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 2
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173", "http://localhost:8080",
        "http://127.0.0.1:5173", "http://127.0.0.1:8080",
    ]

    # 绝对路径，避免 CWD 不同导致找不到/新建空数据库
    SQLALCHEMY_DATABASE_URI: str = f"sqlite:///{os.path.join(DATA_DIR, 'app.db')}"

    @property
    def DATA_DIR(self) -> str:
        """公开数据目录，供备份/附件逻辑使用。"""
        return globals()["DATA_DIR"]

    # 服务运行参数（由系统设置界面维护，写入 .env 文件后由 pydantic-settings 自动加载）
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # ---------- 安全策略 ----------
    # 登录失败阈值 & 锁定分钟数
    LOGIN_FAILURE_LOCK_THRESHOLD: int = 5
    LOGIN_FAILURE_LOCK_MINUTES: int = 15
    # 密码最小长度
    PASSWORD_MIN_LENGTH: int = 8

    # ---------- 灾备 / 数据备份 ----------
    # 备份加密专用密码（强烈建议单独设置；不填将退化为 SECRET_KEY 派生，两者都空则不加密）
    # 建议 32 位以上随机字符串
    BACKUP_ENCRYPTION_PASSWORD: Optional[str] = None

    # 第二备份目录（绝对路径，SMB/NAS/U盘 挂载点即可，例如 /mnt/nas/sems_backups）
    # 要求目录已创建且当前进程有读写权限；空字符串=不启用异地副本
    BACKUP_SECONDARY_DIR: Optional[str] = None

    @property
    def is_default_secret_key(self) -> bool:
        return self.SECRET_KEY in {
            "change-me-in-production-please-use-a-long-random-string",
            "change-me-in-prod",
        }

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
