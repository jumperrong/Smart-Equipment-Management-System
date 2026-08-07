#!/usr/bin/env python3
"""
Windows 打包脚本 — 将后端 + 前端打包为单个 sems.exe
=================================================================

使用方法（在 Windows 上，项目根目录执行）：

    1. 确保 Python 3.10+ 和 Node.js 18+ 已安装
    2. pip install -r backend/requirements.txt
    3. pip install pyinstaller
    4. cd frontend && npm install && npm run build && cd ..
    5. python build_win.py

完成后 dist/sems.exe 即为可分发的单文件程序。
双击运行 → 自动启动后端服务 → 浏览器打开 http://localhost:8000
"""

import os
import subprocess
import shutil
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DIST_OUTPUT = ROOT / "dist"


def step(msg):
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")


def run(cmd, cwd=None):
    print(f"  > {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str))
    if result.returncode != 0:
        print(f"  [ERROR] 命令执行失败 (exit {result.returncode})")
        sys.exit(1)


def build_frontend():
    """构建前端 dist"""
    step("1/4  构建前端 (vite build)")
    if not (FRONTEND / "node_modules").exists():
        run(["npm", "install"], cwd=FRONTEND)
    run(["npm", "run", "build"], cwd=FRONTEND)

    dist_dir = FRONTEND / "dist"
    if not dist_dir.exists():
        print("  [ERROR] 前端构建失败，dist 目录不存在")
        sys.exit(1)
    print(f"  前端构建产物: {dist_dir}")
    return dist_dir


def build_backend(dist_dir):
    """用 PyInstaller 打包后端 + 内嵌前端"""
    step("2/4  PyInstaller 打包后端")

    # 准备 frontend_dist 资源目录（PyInstaller 的 --add-data 参数）
    frontend_dist_src = str(dist_dir).replace("\\", "/")

    # PyInstaller 命令
    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", "sems",
        "--onefile",
        # 入口点
        str(BACKEND / "run_server.py"),
        # 前端静态资源
        "--add-data", f"{frontend_dist_src}{os.pathsep}frontend_dist",
        # 隐式导入
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "sqlalchemy.dialects.sqlite",
        "--hidden-import", "app.api.v1",
        "--hidden-import", "app.models",
        "--hidden-import", "app.services.dashboard_service",
        "--collect-data", "app",
        # 控制台窗口
        "--console",
    ]

    # 添加 icon（如果存在）
    icon = ROOT / "sems.ico"
    if icon.exists():
        pyinstaller_cmd += ["--icon", str(icon)]

    run(pyinstaller_cmd, cwd=ROOT)


def copy_output():
    """复制最终产物"""
    step("3/4  复制产物")
    exe_src = ROOT / "build" / "sems" / "sems.exe"
    if not exe_src.exists():
        # onefile 模式下产物在 dist/ 目录
        exe_src = ROOT / "dist" / "sems.exe"

    if not exe_src.exists():
        print("  [ERROR] 找不到 sems.exe")
        sys.exit(1)

    DIST_OUTPUT.mkdir(exist_ok=True)
    dst = DIST_OUTPUT / "sems.exe"
    shutil.copy2(exe_src, dst)
    print(f"  最终产物: {dst}")
    return dst


def main():
    print("""
╔═══════════════════════════════════════════════════════╗
║          SEMS Windows 单文件打包工具                   ║
║          Semiconductor Equipment Management System     ║
╚═══════════════════════════════════════════════════════╝
    """)

    # 检查 Python 版本
    if sys.version_info < (3, 10):
        print("[ERROR] 需要 Python 3.10+")
        sys.exit(1)

    # 检查 PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("  PyInstaller 未安装，正在安装...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 1. 构建前端
    dist_dir = build_frontend()

    # 2. 打包后端
    build_backend(dist_dir)

    # 3. 复制产物
    exe_path = copy_output()

    # 4. 完成
    step("4/4  打包完成!")
    print(f"""
  ✅ 成功生成: {exe_path}

  使用方法:
    1. 双击 sems.exe 启动
    2. 浏览器访问 http://localhost:8000
    3. 默认账号: admin / admin123

  数据库文件自动创建在 exe 同级 data/ 目录下
  如需修改端口: 设置环境变量 PORT=9000 后再启动
    """)


if __name__ == "__main__":
    main()
