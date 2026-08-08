@echo off
REM ---------------------------------------------------------------------------
REM sems_healthcheck.bat
REM Windows 健康检查脚本：调用 http://127.0.0.1:<PORT>/health，
REM 连续失败 N 次后 自动重启 NSSM 服务（默认服务名 sems）。
REM
REM 用法：
REM   sems_healthcheck.bat                            # 默认 PORT=8000, SERVICE=sems
REM   sems_healthcheck.bat /PORT 8001 /SERVICE myapp  # 自定义
REM   sems_healthcheck.bat /RESTART-AFTER 3           # 连续失败 3 次再重启
REM
REM 配合"任务计划程序"：每 2 分钟触发一次。
REM ---------------------------------------------------------------------------
setlocal EnableDelayedExpansion

set "PORT=8000"
set "SERVICE=sems"
set "RESTART_AFTER=3"
set "STATE_DIR=%ALLUSERSPROFILE%\sems"
set "STATE_FILE=%STATE_DIR%\hc_fail_count.txt"

:PARSE
if "%~1"=="" goto END_PARSE
if /I "%~1"=="/PORT"       ( set "PORT=%~2"& shift & shift & goto PARSE )
if /I "%~1"=="/SERVICE"    ( set "SERVICE=%~2"& shift & shift & goto PARSE )
if /I "%~1"=="/RESTART-AFTER" ( set "RESTART_AFTER=%~2"& shift & shift & goto PARSE )
if /I "%~1"=="/?"      ( goto USAGE )
if /I "%~1"=="/h"      ( goto USAGE )
shift
goto PARSE
:END_PARSE

if NOT EXIST "%STATE_DIR%" mkdir "%STATE_DIR%" 2>nul

set "URL=http://127.0.0.1:%PORT%/health"

REM ---------- 先尝试 PowerShell（稳定），否则找 curl.exe ----------
set "BODY="
set "CODE=1"
where powershell >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    for /f "usebackq delims=" %%L in (`powershell -NoProfile -Command "$resp=''; try { $resp = (Invoke-WebRequest -Uri '%URL%' -UseBasicParsing -TimeoutSec 8).Content } catch { }; Write-Output $resp" 2^>nul`) do set "BODY=%%L"
    if "!BODY!"=="" ( set "CODE=1" ) else (
        echo !BODY! | findstr /i "ok" >nul && set "CODE=0" || set "CODE=1"
    )
) else (
    where curl >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        for /f "usebackq delims=" %%L in (`curl -fsS --max-time 8 "%URL%" 2^>nul`) do set "BODY=%%L"
        if "!BODY!"=="" ( set CODE=1 ) else (
            echo !BODY! | findstr /i "ok" >nul && set "CODE=0" || set "CODE=1"
        )
    )
)

set "NOW=%date% %time%"
if %CODE% EQU 0 (
    echo 0 > "%STATE_FILE%" 2>nul
    echo [%NOW%] [OK] health=OK  body=!BODY!
    exit /B 0
)

REM ---------- 失败：累加 ----------
set "PREV=0"
if EXIST "%STATE_FILE%" (
    set /p PREV=<"%STATE_FILE%" 2>nul
    if "!PREV!"=="" set "PREV=0"
)
set /A NEXT=PREV + 1
echo !NEXT! > "%STATE_FILE%" 2>nul
echo [%NOW%] [FAIL] health=NG (连续失败 !NEXT! / %RESTART_AFTER% 次, body=!BODY!)

if !NEXT! LSS %RESTART_AFTER% exit /B 1

REM ---------- 达到阈值：重启 Windows 服务（NSSM / sc 服务名通用） ----------
sc query "%SERVICE%" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [%NOW%] [WARN] 连续失败 !NEXT! 次，尝试 net stop/start %SERVICE% ...
    net stop "%SERVICE%" >nul 2>nul
    timeout /t 3 /nobreak >nul
    net start "%SERVICE%" >nul
    if !ERRORLEVEL! EQU 0 ( echo [%NOW%] [OK] 已 net start %SERVICE% ) else ( echo [%NOW%] [FAIL] net start %SERVICE% 失败，请查看事件查看器 )
) else (
    echo [%NOW%] [WARN] 服务 %SERVICE% 未注册，跳过重启。建议用 nssm install %SERVICE% 注册。
)
echo 0 > "%STATE_FILE%" 2>nul
exit /B 1

:USAGE
echo sems_healthcheck.bat  [/PORT 8000] [/SERVICE sems] [/RESTART-AFTER 3]
echo   /PORT           后端健康检查端口（默认 8000）
echo   /SERVICE        NSSM 注册的服务名（默认 sems），失败时会 net restart
echo   /RESTART-AFTER  连续失败多少次才真正重启（默认 3）
exit /B 0
