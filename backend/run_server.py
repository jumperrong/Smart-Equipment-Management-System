"""
SEMS 服务启动入口（PyInstaller 打包入口点）
启动后端 → 自动打开浏览器 → 保持运行
"""
import os
import sys
import time
import threading
import webbrowser


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
    """启动后台线程自动打开浏览器"""
    t = threading.Thread(target=open_browser_after_delay, args=(port,), daemon=True)
    t.start()


def main():
    port = int(os.environ.get("PORT", 8000))

    # 自动打开浏览器（仅非 frozen 时不自动开，开发时手动控制）
    if getattr(sys, "frozen", False):
        _start_browser_thread(port)

    print(f"""
╔═══════════════════════════════════════════════╗
║          SEMS 设备管理系统                      ║
║          Semiconductor Equipment Mgmt System   ║
╠═══════════════════════════════════════════════╣
║  服务地址: http://localhost:{port:<23s}║
║  默认账号: admin                               ║
║  默认密码: admin123                             ║
║                                               ║
║  按 Ctrl+C 停止服务                           ║
╚═══════════════════════════════════════════════╝
""")

    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
