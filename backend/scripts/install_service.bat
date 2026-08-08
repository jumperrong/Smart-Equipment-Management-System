@echo off
REM ---------------------------------------------------------------------------
REM install_service.bat
REM 一键把 SEMS 安装为 Windows 服务（开机自启 + 崩溃自重启 + 健康检查计划任务）
REM
REM 依赖：
REM   1) 推荐先装 NSSM：https://nssm.cc/download  （把 nssm.exe 放 PATH，或放 backend/scripts/nssm.exe）
REM      NSSM 可：非 EXE 程序（如 .venv\Scripts\python.exe run_server.py）也能注册成服务、自动重启崩溃
REM   2) 备选：sc.exe + 包装 exe 方式，比较麻烦；本脚本默认 NSSM。
REM
REM 用法（管理员 cmd，或管理员 PowerShell 中 cmd /c install_service.bat）：
REM   install_service.bat                              # 自动探测当前 backend 目录，端口 8000，服务名 sems
REM   install_service.bat  /PORT 8001 /SERVICE myapp   # 自定义端口/服务名
REM   install_service.bat  /PY "D:\sems\backend\.venv\Scripts\python.exe"
REM
REM 做的事：
REM   ① 用 NSSM 注册服务：NSSM 会在崩时自动重启（RestartDelay/Delayed/Throttle）
REM   ② "服务" → 启动类型：自动(延迟启动)，重启策略：第1/2/3次失败都重启，60s 后 reset fail count
REM   ③ 在"任务计划程序"加入 2 分钟跑一次的健康检查，连续失败 3 次让 NSSM 再重启一轮兜底
REM ---------------------------------------------------------------------------
setlocal EnableDelayedExpansion
cd /d "%~dp0"
cd ..
set "BACKEND_DIR=%cd%"
set "RUN_SCRIPT=%BACKEND_DIR%\run_server.py"
set "PORT=8000"
set "SERVICE=sems"
set "PY_EXE="
set "INSTALL_HC=1"

REM ======= 参数解析 =======
:PARSE
if "%~1"=="" goto END_PARSE
if /I "%~1"=="/PORT"     ( set "PORT=%~2"& shift & shift & goto PARSE )
if /I "%~1"=="/SERVICE"  ( set "SERVICE=%~2"& shift & shift & goto PARSE )
if /I "%~1"=="/PY"       ( set "PY_EXE=%~2"& shift & shift & goto PARSE )
if /I "%~1"=="/NO-HC"    ( set "INSTALL_HC=0"& shift & goto PARSE )
if /I "%~1"=="/?"        ( goto USAGE )
if /I "%~1"=="/h"        ( goto USAGE )
shift
goto PARSE
:END_PARSE

echo.
echo ================ SEMS Windows 服务安装 ================
echo BACKEND_DIR = %BACKEND_DIR%
echo SERVICE     = %SERVICE%
echo PORT        = %PORT%
echo ========================================================

if NOT EXIST "%RUN_SCRIPT%" (
    echo [ERROR] 找不到 %RUN_SCRIPT%，请在 backend\scripts 目录内执行本脚本。 & exit /B 2
)

REM ======= 找 python.exe =======
if "%PY_EXE%"=="" (
    if EXIST "%BACKEND_DIR%\.venv\Scripts\python.exe" (
        set "PY_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe"
    ) else (
        where python >nul 2>nul
        if !ERRORLEVEL! EQU 0 ( for /f "delims=" %%P in ('where python') do set "PY_EXE=%%P" & goto :PYFOUND )
        :PYFOUND
    )
)
if "%PY_EXE%"=="" (
    echo [ERROR] 找不到 Python.exe。请 装 Python 或 pip -r 后生成 .venv，或用 /PY 指定路径。 & exit /B 3
)
echo [INFO] Python = %PY_EXE%

REM ======= 找 NSSM =======
set "NSSM="
if EXIST "%~dp0nssm.exe" set "NSSM=%~dp0nssm.exe"
if "%NSSM%"=="" ( where nssm >nul 2>nul && for /f "delims=" %%N in ('where nssm') do set "NSSM=%%N" )
if "%NSSM%"=="" (
    echo [ERROR] 找不到 nssm.exe。请到 https://nssm.cc/download 下载并放到：
    echo         %~dp0nssm.exe
    echo         或者加入 PATH 后再运行。
    exit /B 4
)
echo [INFO] NSSM = %NSSM%

REM ======= 先卸旧同名服务（防重复） =======
sc query "%SERVICE%" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [INFO] 检测到同名服务 %SERVICE%，先停止并移除...
    net stop "%SERVICE%" >nul 2>nul
    timeout /t 2 /nobreak >nul
    "%NSSM%" stop "%SERVICE%" confirm >nul 2>nul
    "%NSSM%" remove "%SERVICE%" confirm >nul
    timeout /t 2 /nobreak >nul
    echo [OK] 旧服务已移除。
)

REM ======= 注册 NSSM 服务 =======
"%NSSM%" install "%SERVICE%" "%PY_EXE%" "%RUN_SCRIPT%"
"%NSSM%" set "%SERVICE%" AppDirectory "%BACKEND_DIR%"
"%NSSM%" set "%SERVICE%" AppStdout "%BACKEND_DIR%\data\logs\nssm.out.log"
"%NSSM%" set "%SERVICE%" AppStderr "%BACKEND_DIR%\data\logs\nssm.err.log"
"%NSSM%" set "%SERVICE%" AppRotateFiles 1
"%NSSM%" set "%SERVICE%" AppRotateBytes 10485760
REM 崩溃自动重启：立即（RestartDelay 0ms 但加了 AppThrottle 节流）
"%NSSM%" set "%SERVICE%" AppRestartDelay 0
"%NSSM%" set "%SERVICE%" AppThrottle 1500
REM 服务停止退出码以外的 exit 都算失败：Restart on exit = non-zero + Any crash
"%NSSM%" set "%SERVICE%" AppExit Default Restart
REM 环境变量（uvicorn 吃这些）
"%NSSM%" set "%SERVICE%" AppEnvironmentExtra "PYTHONUNBUFFERED=1" "SEMS_OPEN_BROWSER=0" "PORT=%PORT%" "HOST=0.0.0.0" "SEMS_LOG_DIR=%BACKEND_DIR%\data\logs" "PYTHONIOENCODING=utf-8"
"%NSSM%" set "%SERVICE%" DisplayName "SEMS 设备管理系统后端 (%SERVICE%)"
"%NSSM%" set "%SERVICE%" Description "Semiconductor Equipment Management System backend service. 由 NSSM 守护，进程挂了自动拉起。"

REM ======= 服务启动类型 & 重启策略（用 sc config / sc failure 配置） =======
sc config "%SERVICE%" start= delayed-auto
REM 三次失败都"重新启动服务"，间隔 3000ms；失败计数 86400 秒后重置
sc failure "%SERVICE%" reset= 86400 actions= restart/3000/restart/3000/restart/3000

REM ======= 启动服务 =======
echo [INFO] 服务已安装，现在启动...
net start "%SERVICE%"
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] 启动失败。请用： nssm edit %SERVICE% 手动检查，或查看 data\logs\nssm.err.log
    echo        常见原因：.env 权限不足 / data 目录只读 / 端口 %PORT% 被占用
)

REM ======= 健康检查计划任务（每 2 分钟） =======
if "%INSTALL_HC%"=="1" (
    echo [INFO] 注册「健康检查」计划任务（每 2 分钟，连续失败 3 次再重启 %SERVICE%）
    set "HC=%~dp0sems_healthcheck.bat"
    schtasks /Create /F /TN "SEMS健康检查_%SERVICE%" /SC MINUTE /MO 2 ^
        /TR "\"!HC!\" /PORT %PORT% /SERVICE %SERVICE% /RESTART-AFTER 3" ^
        /RL HIGHEST
    echo [OK] 计划任务已创建：schtasks /Run /TN "SEMS健康检查_%SERVICE%"
)

echo.
echo ================ 安装完成 ================
echo 服务管理：
echo   启动：  net start %SERVICE%
echo   停止：  net stop  %SERVICE%
echo   重启：  net stop %SERVICE% ^& net start %SERVICE%
echo   编辑：  nssm edit %SERVICE%   （看 stderr/stdout 路径）
echo 日志位置：
echo   "%BACKEND_DIR%\data\logs\sems.log"  (Python 应用按天轮转 14 天)
echo   "%BACKEND_DIR%\data\logs\sems.error.log"
echo   事件查看器 → 应用程序日志：NSSM 挂服务的退出码、重启记录
echo 健康验证（本机 cmd）：
echo   curl -fsS http://127.0.0.1:%PORT%/health
echo 卸载：管理员 cmd 执行  nssm stop %SERVICE% ^& nssm remove %SERVICE% confirm
exit /B 0

:USAGE
echo install_service.bat  [/PORT 8000] [/SERVICE sems] [/PY "path\python.exe"] [/NO-HC]
echo   /PORT      服务监听端口（默认 8000）
echo   /SERVICE   注册到 Windows 的服务名（默认 sems）
echo   /PY        指定 Python 可执行文件（默认自动找 .venv\Scripts\python.exe / PATH 中 python）
echo   /NO-HC     不安装健康检查的计划任务（默认安装）
exit /B 0
