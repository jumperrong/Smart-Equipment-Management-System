"""
SEMS 服务启动入口（PyInstaller 打包 / systemd / NSSM / 前台运行 通用入口）。

健壮性特性：
- 启动时预热（初始化数据库 + 校验默认用户 + 注册生命周期事件）。
- 端口占用友好提示（不是 OSError 栈，而是「端口 xxxx 已被占用，请换端口或停旧进程」+ 检测占用进程 PID 提示）。
- SQLite WAL checkpoint 钩子：startup 强制 checkpoint + PRAGMA；shutdown 前再 checkpoint 一次，
  避免 -wal/-shm 意外残留、下次启动恢复失败。
- uvicorn 配置调优：
    * timeout_keep_alive：避免反向代理层频繁断连（默认 5s 对 Nginx 默认 75s 太激进）
    * graceful_timeout：给正在处理的请求 30s 收尾时间，避免 Ctrl-C/systemctl restart 直接杀
    * h11_max_incomplete_event_size：防慢连接/大包头
    * log_config：自定义控制台 + 文件日誌（文件日誌按天轮转，保留 14 天）
    * workers=1：用 APScheduler/内存态的场景不能多 worker；如果需要多 worker 请把定时/缓存迁移外部
- 所有启动参数可用环境变量覆盖：
    PORT / HOST / UVICORN_WORKERS / UVICORN_LOG_LEVEL / SEMS_LOG_DIR / SEMS_OPEN_BROWSER
"""
import os
import socket
import sys
import time
import threading
import webbrowser
import logging
from logging.handlers import TimedRotatingFileHandler


def _detect_port_owner(port: int):
    """尽力检测某 TCP 端口的占用进程（Linux/Windows 都尝试用系统命令）。
    返回字符串（可能包含 PID/进程名）或 None。
    """
    try:
        import subprocess, shlex
        if os.name == "nt":
            # Windows: netstat -ano | findstr :<port>
            out = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True, timeout=5
            ).stdout or ""
            lines = [ln for ln in out.splitlines() if f":{port}" in ln and ("LISTENING" in ln or "ESTABLISHED" in ln)]
            pids = set()
            for ln in lines:
                parts = ln.split()
                if parts:
                    pids.add(parts[-1])
            if pids:
                return f"占用端口 {port} 的 PID 可能为 {sorted(pids)}。可用「任务管理器 → 详细信息」定位，或执行 TaskKill /F /PID <号>"
            return None
        # Linux/macOS
        for cmd in (
            ["ss", "-ltnp"],
            ["lsof", f"-iTCP:{port}", "-sTCP:LISTEN", "-P", "-n"],
            ["fuser", f"{port}/tcp"],
        ):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            except FileNotFoundError:
                continue
            if r.returncode == 0 and r.stdout.strip():
                return f"占用端口 {port} 的信息：\n{r.stdout.strip()}\n可用 `kill <PID>` 停掉旧进程。"
    except Exception:
        return None
    return None


def _check_port_available(host: str, port: int) -> None:
    """预检查端口可用性，避免后续 uvicorn 的 OSError 栈信息晦涩。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host if host not in ("", "0.0.0.0", "::") else "0.0.0.0", port))
    except OSError as e:
        owner = _detect_port_owner(port)
        msg = f"[SEMS] 无法启动：端口 {port} 已被占用。\n  可选择：\n    1) 停掉占用 {port} 的旧进程后重试。\n    2) 换端口启动：Windows `set PORT=8001`，Linux `export PORT=8001` 后再运行。\n    3) 若运行在容器内，修改 -p 8001:8000 的主机端口映射。"
        if owner:
            msg += "\n" + owner
        msg += f"\n原始错误：{e}"
        print(msg, file=sys.stderr)
        sys.exit(2)
    finally:
        try:
            s.close()
        except Exception:
            pass


def open_browser_after_delay(port: int):
    """延迟 2 秒后自动打开浏览器"""
    time.sleep(2)
    url = f"http://localhost:{port}"
    try:
        webbrowser.open(url)
        print(f"  浏览器已打开: {url}")
    except Exception:
        print(f"  请手动访问: {url}")


def _start_browser_thread(port: int):
    t = threading.Thread(target=open_browser_after_delay, args=(port,), daemon=True)
    t.start()


def _build_log_config(log_dir: str, level: str) -> dict:
    """返回一个传给 uvicorn.run 的 log_config 字典。
    目标：控制台保留 INFO；同时按天滚动写文件，保留 14 天；ERROR 再单独出 error.log。
    """
    # logging.setLevel() 必须是大写的 INFO/WARNING/...，这里统一大写
    level = (level or "INFO").upper()
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        log_dir = None

    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatters = {
        "default": {"()": "uvicorn.logging.DefaultFormatter", "fmt": fmt, "datefmt": datefmt, "use_colors": None},
        "access": {"()": "uvicorn.logging.AccessFormatter", "fmt": "%(asctime)s | %(levelname)-7s | %(client_addr)s | %(request_line)s | %(status_code)s", "datefmt": datefmt, "use_colors": None},
    }
    handlers = {
        "default": {"class": "logging.StreamHandler", "formatter": "default", "stream": "ext://sys.stderr"},
        "access": {"class": "logging.StreamHandler", "formatter": "access", "stream": "ext://sys.stdout"},
    }
    loggers = {
        "uvicorn": {"handlers": ["default"], "level": level, "propagate": False},
        "uvicorn.error": {"level": level},
        "uvicorn.access": {"handlers": ["access"], "level": level, "propagate": False},
        "casbin": {"level": "WARNING"},
    }

    if log_dir:
        info_handler = TimedRotatingFileHandler(
            filename=os.path.join(log_dir, "sems.log"),
            when="midnight",
            interval=1,
            backupCount=14,
            encoding="utf-8",
        )
        info_handler.setFormatter(logging.Formatter(fmt, datefmt))
        error_handler = TimedRotatingFileHandler(
            filename=os.path.join(log_dir, "sems.error.log"),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.WARNING)
        error_handler.setFormatter(logging.Formatter(fmt, datefmt))

        handlers["default_file"] = {"class": "logging.handlers.TimedRotatingFileHandler",
                                    "formatter": "default",
                                    "filename": info_handler.baseFilename,
                                    "when": "midnight", "interval": 1, "backupCount": 14, "encoding": "utf-8"}
        handlers["error_file"] = {"class": "logging.handlers.TimedRotatingFileHandler",
                                  "formatter": "default",
                                  "filename": error_handler.baseFilename,
                                  "when": "midnight", "interval": 1, "backupCount": 30, "encoding": "utf-8",
                                  "level": "WARNING"}
        loggers["uvicorn"]["handlers"] = ["default", "default_file", "error_file"]
        loggers["uvicorn.access"]["handlers"] = ["access", "default_file"]

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "loggers": loggers,
    }


def _sqlite_pre_start_checkpoint(db_uri: str) -> None:
    """在接收请求前把 SQLite WAL 文件 checkpoint 回主库，避免启动带着脏 WAL。"""
    if not db_uri.startswith("sqlite://"):
        return
    # SQLALCHEMY_DATABASE_URI 通常是 sqlite:///./data/app.db 或 sqlite:////abs/path
    path_part = db_uri.replace("sqlite://", "")
    # sqlalchemy 用 4 个斜杠表示绝对路径：sqlite:////abs/app.db → /abs/app.db；3 斜相对：sqlite:///./app.db → ./app.db
    if path_part.startswith("///"):  # 相对路径：///./data/app.db
        db_path = path_part[2:]
    elif path_part.startswith("//") and len(path_part) > 2 and path_part[2] == "/":
        db_path = path_part[2:]
    elif path_part.startswith("//"):
        db_path = path_part[1:]
    else:
        db_path = path_part
    db_path = os.path.abspath(db_path)
    if not os.path.exists(db_path):
        return
    try:
        import sqlite3
        conn = sqlite3.connect(db_path, timeout=10.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA wal_autocheckpoint=1000;")
            conn.execute("PRAGMA optimize;")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.commit()
        finally:
            conn.close()
        print(f"[SEMS] SQLite 预热 checkpoint 完成: {db_path}")
    except Exception as e:
        print(f"[SEMS] SQLite 预热 checkpoint 跳过（非致命）: {e}")


def main():
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    workers = max(1, int(os.environ.get("UVICORN_WORKERS", 1)))
    log_level = str(os.environ.get("UVICORN_LOG_LEVEL", "info")).lower()
    log_dir = os.environ.get("SEMS_LOG_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "logs"))

    # 是否自动开浏览器：打包 exe 前台双击才默认开；systemd/NSSM/docker 会设置 SEMS_OPEN_BROWSER=0
    env_open = os.environ.get("SEMS_OPEN_BROWSER", "")
    if env_open in ("0", "false", "no"):
        open_browser = False
    elif env_open in ("1", "true", "yes"):
        open_browser = True
    else:
        open_browser = bool(getattr(sys, "frozen", False))

    # 启动前基础检查
    print(f"[SEMS] 预检查：监听 {host}:{port}；workers={workers}；log_level={log_level}")
    _check_port_available(host, port)

    # SQLite WAL checkpoint 预热（仅 sqlite，在 uvicorn 启监听前做）
    from app.core.config import settings as _settings
    _sqlite_pre_start_checkpoint(_settings.SQLALCHEMY_DATABASE_URI)

    # 应用级初始化：建表 / 默认用户 / 默认设置 / 启动 APScheduler
    from app.main import create_app, _bootstrap_once
    _bootstrap_once()

    # 日志配置
    log_config = _build_log_config(log_dir, log_level)

    print(f"""
╔══════════════════════════════════════════════════╗
║           SEMS 半导体制造执行系统                  ║
║      Semiconductor Manufacturing Execution Sys. ║
╠══════════════════════════════════════════════════╣
║  服务地址: http://localhost:{port!s:<24}║
║  健康检查: http://localhost:{port!s}/health         ║
║  API 文档: http://localhost:{port!s}/docs           ║
║  日志目录: {log_dir:<34s}║
║  默认账号: admin                                    ║
║  默认密码: admin123 （首次登录强制改密）              ║
║                                                    ║
║  停止服务: 按 Ctrl+C  / systemctl stop sems        ║
║            docker compose down / NSSM 管理工具     ║
╚══════════════════════════════════════════════════╝
""")

    if open_browser:
        _start_browser_thread(port)

    import uvicorn
    try:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=False,
            workers=workers,
            log_level=log_level,
            log_config=log_config,
            # 连接存活参数（前端长连接/反向代理友好）
            timeout_keep_alive=75,
            timeout_graceful_shutdown=30,
            h11_max_incomplete_event_size=64 * 1024,
            # 生命周期事件（startup/shutdown）已经通过 FastAPI lifespan 注册
        )
    finally:
        # 退出前再 checkpoint 一次 SQLite：避免停服务时只写了 -wal
        try:
            from app.core.config import settings as _s2
            _sqlite_pre_start_checkpoint(_s2.SQLALCHEMY_DATABASE_URI)
            print("[SEMS] 退出前 SQLite checkpoint 完成。")
        except Exception:
            pass
        print("[SEMS] 服务已退出。")


if __name__ == "__main__":
    main()

