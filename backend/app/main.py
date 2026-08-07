from contextlib import asynccontextmanager
import os
import sys
import pathlib
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.database import Base, engine, SessionLocal, ensure_columns
from app.api.v1 import api_router
from app.services.user_service import init_default_admin
from app.services.dictionary_service import init_seed_dictionary
from app.services.dashboard_service import (
    seed_demo_statuses, seed_demo_spare_parts,
    seed_demo_equipment, seed_demo_inspections,
)
from app.services.permission_service import seed_default_permissions
from app.services.system_setting_service import seed_default_settings
from app.services.restart_service import is_recently_restarted, clear_restart_marker
from app.services import backup_scheduler


def _get_frontend_dist() -> str | None:
    """查找前端构建产物目录（PyInstaller 打包后内嵌 / 开发模式）"""
    # 1) 环境变量指定
    env_path = os.environ.get("FRONTEND_DIST")
    if env_path and os.path.isdir(env_path):
        return env_path
    # 2) PyInstaller 打包：资源在 _MEIPASS 或 exe 同级 frontend_dist
    if getattr(sys, "frozen", False):
        base = pathlib.Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else pathlib.Path(sys.executable).parent
        candidates = [
            base / "frontend_dist",
            pathlib.Path(sys.executable).parent / "frontend_dist",
        ]
        for c in candidates:
            if c.is_dir():
                return str(c)
    # 3) 开发模式：项目根目录下的 frontend/dist
    dev_path = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if dev_path.is_dir():
        return str(dev_path)
    return None


def ensure_db_dir():
    db_uri = settings.SQLALCHEMY_DATABASE_URI
    if db_uri.startswith("sqlite:///"):
        path = db_uri[len("sqlite:///"):]
        d = os.path.dirname(path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)


def init_db():
    ensure_db_dir()
    Base.metadata.create_all(bind=engine)
    ensure_columns()  # 轻量迁移：补齐新增列(如 spare_parts.unit_price)
    db = SessionLocal()
    try:
        init_default_admin(db)
        init_seed_dictionary(db)
        seed_default_permissions(db)  # 角色权限矩阵初始化（保留管理员调整）
        seed_default_settings(db)     # 系统设置初始化（环境变量默认值）
        _seed_ip_whitelist_defaults(db)  # IP 白名单默认项（127.0.0.1, 局域网段）
        seed_demo_equipment(db)    # 演示数据：创建10台半导体设备（须在 statuses 之前）
        seed_demo_statuses(db)     # 演示数据：为设备分配各种状态+PM计划
        seed_demo_spare_parts(db)  # 演示数据：生成备件、库存与出入库流水
        seed_demo_inspections(db)  # 演示数据：生成点检模板+检查项+历史记录
        _backfill_process_doc_versions(db)  # 工艺文件版本元信息回填

        # 清理过期重启标记
        if is_recently_restarted():
            clear_restart_marker()
    finally:
        db.close()


def _backfill_process_doc_versions(db) -> None:
    """回填工艺文件的版本元信息(group_id/version_seq/is_latest)。"""
    from app.api.v1.process_document import backfill_version_meta
    try:
        n = backfill_version_meta(db)
        if n:
            print(f"[init] 工艺文件版本元信息回填: {n} 条")
    except Exception as e:
        print(f"[init] 工艺文件版本回填失败(忽略): {e}")


def _seed_ip_whitelist_defaults(db) -> None:
    """预置 IP 白名单默认项（127.0.0.1 / ::1 / 局域网网段）。

    白名单默认禁用，启用后这些预设项才生效。
    """
    from app.models import IPWhitelist
    defaults = [
        ("127.0.0.1", "本机 IPv4"),
        ("::1", "本机 IPv6"),
        ("10.0.0.0/8", "A 类私有网段"),
        ("172.16.0.0/12", "B 类私有网段"),
        ("192.168.0.0/16", "C 类私有网段"),
    ]
    for ip, label in defaults:
        existing = db.query(IPWhitelist).filter(IPWhitelist.ip == ip).first()
        if existing is None:
            db.add(IPWhitelist(ip=ip, label=label, is_active=True))
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    backup_scheduler.start_scheduler()
    yield
    backup_scheduler.stop_scheduler()


def _get_client_ip(request: Request) -> str:
    """从请求中提取客户端真实 IP。

    支持反向代理（nginx 等）的 X-Forwarded-For / X-Real-IP 头。
    """
    # 优先：X-Forwarded-For 第一个 IP（可能为 "client, proxy1, proxy2"）
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # 取第一个
        ip = xff.split(",")[0].strip()
        if ip:
            return ip
    # 次选：X-Real-IP
    xri = request.headers.get("x-real-ip")
    if xri:
        return xri.strip()
    # 兜底：starlette client
    if request.client:
        return request.client.host
    return ""


class IPFilterMiddleware(BaseHTTPMiddleware):
    """IP 白名单过滤中间件。

    - 白名单未启用：放行所有
    - 白名单启用：检查 client IP，不在白名单返回 403 并记录到 access_log
    - 本机 IP (127.0.0.1/::1) 永远放行，避免锁死
    - /api/v1/auth/login 等登录路径不拦截（避免登录也被拦截）
    """

    # 不拦截的路径前缀（避免管理员被锁死）
    EXEMPT_PREFIXES = (
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/system/settings/restart-server",  # 重启接口不拦截
        "/health",
    )

    async def dispatch(self, request: Request, call_next):
        # 健康检查和登录接口放行
        path = request.url.path
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)

        # 懒加载避免启动时循环依赖
        from app.services import ip_filter_service
        from app.services.ip_filter_service import is_ip_allowed, log_access_attempt

        client_ip = _get_client_ip(request)

        # 使用独立 DB session
        db = SessionLocal()
        try:
            if is_ip_allowed(db, client_ip):
                return await call_next(request)

            # 未通过白名单，记录访问日志
            log_access_attempt(
                db,
                ip=client_ip,
                path=path,
                method=request.method,
                user_agent=request.headers.get("user-agent"),
            )

            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"IP {client_ip} 不在白名单内，已记录待管理员审核",
                    "ip": client_ip,
                    "code": "IP_NOT_ALLOWED",
                },
            )
        finally:
            db.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS + ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # IP 白名单过滤中间件（CORS 之后、路由之前）
    app.add_middleware(IPFilterMiddleware)
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/health")
    def root_health():
        return {"status": "ok", "project": settings.PROJECT_NAME}

    # ---- 生产模式：托管前端静态文件 ----
    dist_path = _get_frontend_dist()
    if dist_path:
        # 挂载静态资源目录（js/css/图片等）
        assets_dir = os.path.join(dist_path, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        # SPA fallback：所有非 /api、非 /health 的 GET 请求返回 index.html
        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str, request: Request):
            # 排除 API 路径
            if full_path.startswith("api/") or full_path == "health":
                from fastapi import HTTPException
                raise HTTPException(status_code=404)
            index_file = os.path.join(dist_path, "index.html")
            if os.path.isfile(index_file):
                return FileResponse(index_file)
            from fastapi import HTTPException
            raise HTTPException(status_code=404)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
