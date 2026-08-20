from contextlib import asynccontextmanager
import os
import sys
import pathlib
import time
import secrets

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


# ---------- 启动时安全检查 ----------
def _boot_security_checks():
    """启动时安全检查 + 必要的一次性修复：
    1) 若使用默认 SECRET_KEY → 生成安全随机值写入 .env，并警告退出（避免生产误用）。
    2) 告警：管理员仍使用默认弱密码 admin123 的提示（实际改密在首次登录）。
    """
    if settings.is_default_secret_key:
        print("\n" + "=" * 70)
        print("[SECURITY WARN] 检测到默认 SECRET_KEY，正在生成安全随机密钥并写入 .env ...")
        new_key = secrets.token_urlsafe(48)
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        env_path = os.path.abspath(env_path)
        try:
            existing = ""
            if os.path.isfile(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    existing = f.read()
            lines = existing.splitlines()
            replaced = False
            new_lines = []
            for line in lines:
                s = line.strip()
                if s.startswith("SECRET_KEY=") or s.startswith("SECRET_KEY "):
                    new_lines.append(f"SECRET_KEY={new_key}")
                    replaced = True
                else:
                    new_lines.append(line)
            if not replaced:
                new_lines.append(f"SECRET_KEY={new_key}")
            with open(env_path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
            print(f"[SECURITY OK] 已将新的 SECRET_KEY 写入 {env_path}")
            print("[SECURITY NOTE] 请重启服务以加载新的 SECRET_KEY（旧会话/令牌将失效，需重新登录）。")
        except Exception as e:
            print(f"[SECURITY ERROR] 写入 .env 失败：{e}")
            print(
                "[SECURITY ERROR] 请手动在 .env 中添加 SECRET_KEY=<强随机字符串>，"
                "并禁止使用默认值，否则所有令牌可能被伪造！"
            )
        print("=" * 70 + "\n")

    # CORS 仍含通配符的告警（本应不会，但防御性检查）
    origins = settings.BACKEND_CORS_ORIGINS
    if not origins or "*" in origins:
        print("[SECURITY WARN] BACKEND_CORS_ORIGINS 为空或包含 *，局域网环境建议配置实际来源地址。")
    print(
        f"[SECURITY] CORS 白名单 = {origins or []}；"
        f"access_token={settings.ACCESS_TOKEN_EXPIRE_MINUTES}min；"
        f"refresh_token={settings.REFRESH_TOKEN_EXPIRE_DAYS}d；"
        f"登录失败锁定阈值={settings.LOGIN_FAILURE_LOCK_THRESHOLD}次/"
        f"{settings.LOGIN_FAILURE_LOCK_MINUTES}min；密码最小长度={settings.PASSWORD_MIN_LENGTH}"
    )


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


_BOOTSTRAP_DONE = False


def _bootstrap_once() -> None:
    """幂等的应用级启动前预热。run_server/systemd/NSSM 都在启监听前调用它。

    做的事：
    - 启动安全检查（SECRET_KEY 默认值写 .env、CORS 告警、策略打印）
    - init_db：建表 + 默认用户 + 字典/权限/设置/演示数据回填 + 重启标记清理
    - 不启动 APScheduler（scheduler 属于 lifespan，随 uvicorn 启动；重复 start 会被内部去重）
    """
    global _BOOTSTRAP_DONE
    if _BOOTSTRAP_DONE:
        return
    _boot_security_checks()
    init_db()
    _BOOTSTRAP_DONE = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    _boot_security_checks()
    init_db()
    backup_scheduler.start_scheduler()
    # PM 到期提醒扫描调度器（每天 8:00 扫描 7 天内到期计划写审计日志）
    try:
        from app.services import pm_reminder_service
        pm_reminder_service.start_pm_reminder_scheduler()
    except Exception as e:
        print(f"[SEMS] PM 提醒调度器启动失败（非致命）: {e}")
    yield
    backup_scheduler.stop_scheduler()
    try:
        from app.services import pm_reminder_service
        pm_reminder_service.stop_pm_reminder_scheduler()
    except Exception:
        pass


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
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=600,
    )
    # IP 白名单过滤中间件（CORS 之后、路由之前）
    app.add_middleware(IPFilterMiddleware)

    # 安全响应头中间件（X-Content-Type-Options/X-Frame-Options/CSP 等）
    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            response = await call_next(request)
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self' ws: wss:;"
                "frame-ancestors 'self'; base-uri 'self'; form-action 'self'",
            )
            response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            return response

    app.add_middleware(SecurityHeadersMiddleware)
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
