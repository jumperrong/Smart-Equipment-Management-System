"""服务重启服务。

设计：
- 通过启动一个 detached 子进程后让当前进程退出
- Linux: nohup python -m uvicorn app.main:app ...
- Windows (打包): cmd /c start "" sems.exe
- Windows (开发): subprocess.Popen with CREATE_NEW_PROCESS_GROUP

通过标记文件机制：
- 写 .restart_marker 文件
- 启动新进程
- os._exit(0) 退出当前进程
"""
import os
import sys
import subprocess
import pathlib
from datetime import datetime


def _marker_file() -> pathlib.Path:
    """标记文件路径。"""
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).parent / ".restart_marker"
    return pathlib.Path.cwd() / ".restart_marker"


def restart_server() -> dict:
    """重启当前服务。

    流程：
    1. 写 .restart_marker 文件
    2. 启动 detached 子进程（新进程）
    3. os._exit(0) 退出当前进程

    返回 dict（在子进程启动前返回给前端）。
    """
    # 写标记
    marker = _marker_file()
    try:
        marker.write_text(
            f"restarted_at={datetime.utcnow().isoformat()}\n"
            f"pid={os.getpid()}\n",
            encoding="utf-8",
        )
    except Exception as e:
        return {"ok": False, "error": f"无法写标记文件: {e}"}

    # 获取当前启动参数
    port = os.environ.get("PORT", "8000")
    host = os.environ.get("HOST", "0.0.0.0")

    if getattr(sys, "frozen", False):
        # Windows 打包模式：启动新的 sems.exe
        exe_path = sys.executable
        try:
            # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
            subprocess.Popen(
                [exe_path],
                creationflags=0x00000008 | 0x00000200,  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                close_fds=True,
            )
        except Exception as e:
            return {"ok": False, "error": f"启动新进程失败: {e}"}
    else:
        # 开发模式：用相同 Python + uvicorn 启动
        cwd = str(pathlib.Path(__file__).resolve().parent.parent)  # backend/
        env = os.environ.copy()
        # 子进程继承环境变量（含 PORT/HOST）
        try:
            # Linux: nohup 起到 detached
            if sys.platform.startswith("linux") or sys.platform == "darwin":
                subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "app.main:app",
                     "--host", host, "--port", str(port), "--log-level", "info"],
                    cwd=cwd,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                    close_fds=True,
                )
            else:
                # Windows 开发模式
                subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "app.main:app",
                     "--host", host, "--port", str(port), "--log-level", "info"],
                    cwd=cwd,
                    env=env,
                    creationflags=0x00000008 | 0x00000200,
                    close_fds=True,
                )
        except Exception as e:
            return {"ok": False, "error": f"启动新进程失败: {e}"}

    # 启动新进程成功，1 秒后退出当前进程
    import threading
    def _delayed_exit():
        import time
        time.sleep(1.0)
        # 让响应先返回
        os._exit(0)

    t = threading.Thread(target=_delayed_exit, daemon=True)
    t.start()

    return {
        "ok": True,
        "message": "重启指令已发出，新进程正在启动，请稍候...",
        "old_pid": os.getpid(),
        "port": port,
        "host": host,
        "marker_file": str(marker),
    }


def is_recently_restarted() -> bool:
    """检查是否最近被重启过（标记文件存在且时间戳在 5 分钟内）。"""
    marker = _marker_file()
    if not marker.exists():
        return False
    try:
        content = marker.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("restarted_at="):
                ts = line.split("=", 1)[1].strip()
                try:
                    restarted_at = datetime.fromisoformat(ts)
                    age = (datetime.utcnow() - restarted_at).total_seconds()
                    return 0 <= age < 300  # 5 分钟内
                except (ValueError, TypeError):
                    continue
    except Exception:
        pass
    return False


def clear_restart_marker() -> None:
    """清除重启标记。"""
    marker = _marker_file()
    try:
        if marker.exists():
            marker.unlink()
    except Exception:
        pass
