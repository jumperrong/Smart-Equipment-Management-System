@echo off
REM ---------------------------------------------------------------------------
REM sems_standalone_backup.bat
REM Windows 系统级独立备份脚本（不依赖 Python/Java/服务进程）。
REM 适用：局域网 Windows Server 部署 SEMS 的场景，配合"任务计划程序"定时跑。
REM
REM 要求：
REM   - 已安装 Python 3（打包 zip；若没装，本机至少要有 PowerShell 5+）
REM   - 可选：sqlite3.exe 放入 PATH 或 SEMS_BACKEND_DIR\tools\sqlite3.exe
REM   - 可选：openssl.exe 放入 PATH（启用加密时）
REM
REM 配置方式（三选一，优先级从高到低）：
REM   1) 运行：sems_standalone_backup.bat D:\sems\backup.conf  （conf 里写 set KEY=VAL）
REM   2) 先 set 环境变量再运行
REM   3) 直接改本脚本下方 "SET_DEFAULT_AREA"
REM
REM 输出结构：
REM   %SEMS_PRIMARY_DIR%\sems_standalone_YYYYmmdd_HHMMSS.zip
REM   %SEMS_PRIMARY_DIR%\sems_standalone_YYYYmmdd_HHMMSS.zip.enc    (设置了 SEMS_ENC_PASSWORD)
REM   然后复制一份到 %SEMS_SECONDARY_DIR% (如设置)
REM ---------------------------------------------------------------------------
setlocal EnableDelayedExpansion

:SET_DEFAULT_AREA
    if "!SEMS_BACKEND_DIR!"=="" set "SEMS_BACKEND_DIR=%~dp0.."
    if "!SEMS_PRIMARY_DIR!"=="" set "SEMS_PRIMARY_DIR=!SEMS_BACKEND_DIR!\data\backups\standalone"
    if "!SEMS_SECONDARY_DIR!"=="" set "SEMS_SECONDARY_DIR="
    if "!SEMS_ENC_PASSWORD!"=="" set "SEMS_ENC_PASSWORD="
    if "!SEMS_KEEP_LOCAL!"=="" set "SEMS_KEEP_LOCAL=30"
    if "!SEMS_KEEP_SECONDARY!"=="" set "SEMS_KEEP_SECONDARY=14"
    if "!SEMS_INCLUDE_UPLOADS!"=="" set "SEMS_INCLUDE_UPLOADS=1"
    if "!SEMS_INCLUDE_ENV!"=="" set "SEMS_INCLUDE_ENV=1"

REM 如果带参数且存在，则 call 它（批处理也能做 set 变量）
if NOT "%~1"=="" if EXIST "%~1" (
    echo [INFO] 读取配置文件: %~1
    call "%~1"
)

REM 检查 backend 目录
if NOT EXIST "!SEMS_BACKEND_DIR!" (
    echo [ERROR] SEMS_BACKEND_DIR=!SEMS_BACKEND_DIR! 不存在
    exit /B 2
)

pushd "!SEMS_BACKEND_DIR!"

set "DATA_DIR=!SEMS_BACKEND_DIR!\data"
set "DB_FILE=!DATA_DIR!\app.db"
set "UPLOADS_DIR=!DATA_DIR!\uploads"
set "ENV_FILE=!SEMS_BACKEND_DIR!\.env"

if NOT EXIST "!SEMS_PRIMARY_DIR!" mkdir "!SEMS_PRIMARY_DIR!"

REM 临时工作目录：%TEMP%
set "TS=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TS=!TS: =0!"
set "TMP_ROOT=%TEMP%\sems_backup_!TS!"
if EXIST "!TMP_ROOT!" rd /S /Q "!TMP_ROOT!"
mkdir "!TMP_ROOT!"

echo [%date% %time%] ==== 开始独立备份 ts=!TS! ====
echo backend=!SEMS_BACKEND_DIR!
echo primary=!SEMS_PRIMARY_DIR!
if NOT "!SEMS_SECONDARY_DIR!"=="" (echo secondary=!SEMS_SECONDARY_DIR!) else (echo secondary=(未启用))
if NOT "!SEMS_ENC_PASSWORD!"=="" (echo encryption=enabled) else (echo encryption=disabled)

REM ---------------------------------------------------------------------
REM 1) SQLite 一致性快照（有 sqlite3.exe 就用 .backup；否则直拷贝）
REM ---------------------------------------------------------------------
set "DB_SNAP=!TMP_ROOT!\app.db"
if EXIST "!DB_FILE!" (
    where sqlite3 >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        sqlite3 "!DB_FILE!" ".backup '!DB_SNAP!'"
        if !ERRORLEVEL! NEQ 0 (
            echo [WARN] sqlite3 .backup 失败，改为文件复制
            copy /Y "!DB_FILE!" "!DB_SNAP!" >nul
            if EXIST "!DB_FILE!-wal" copy /Y "!DB_FILE!-wal" "!DB_SNAP!-wal" >nul
            if EXIST "!DB_FILE!-shm" copy /Y "!DB_FILE!-shm" "!DB_SNAP!-shm" >nul
        ) else (
            echo [OK] sqlite3 快照成功
        )
    ) else (
        echo [WARN] 未检测到 sqlite3.exe，改为文件复制；建议安装 sqlite-tools-win
        copy /Y "!DB_FILE!" "!DB_SNAP!" >nul
        if EXIST "!DB_FILE!-wal" copy /Y "!DB_FILE!-wal" "!DB_SNAP!-wal" >nul
        if EXIST "!DB_FILE!-shm" copy /Y "!DB_FILE!-shm" "!DB_SNAP!-shm" >nul
    )
) else (
    echo [WARN] !DB_FILE! 不存在（全新环境）
)

REM ---------------------------------------------------------------------
REM 2) 打包 zip（优先用 python，其次用 PowerShell Compress-Archive）
REM ---------------------------------------------------------------------
set "ZIP_NAME=sems_standalone_!TS!.zip"
set "ZIP_PATH=!SEMS_PRIMARY_DIR!\!ZIP_NAME!"
set "PACK_DIR=!TMP_ROOT!\pack"
mkdir "!PACK_DIR!"

if EXIST "!DB_SNAP!" copy /Y "!DB_SNAP!" "!PACK_DIR!\app.db" >nul
if EXIST "!DB_SNAP!-wal" copy /Y "!DB_SNAP!-wal" "!PACK_DIR!\app.db-wal" >nul
if EXIST "!DB_SNAP!-shm" copy /Y "!DB_SNAP!-shm" "!PACK_DIR!\app.db-shm" >nul

if "!SEMS_INCLUDE_ENV!"=="1" if EXIST "!ENV_FILE!" copy /Y "!ENV_FILE!" "!PACK_DIR!\.env" >nul

if "!SEMS_INCLUDE_UPLOADS!"=="1" if EXIST "!UPLOADS_DIR!" (
    xcopy /E /I /Y /Q "!UPLOADS_DIR!" "!PACK_DIR!\uploads\" >nul
)

REM 写 manifest
set "MANIFEST=!PACK_DIR!\_backup_manifest.json"
(
echo {
echo   "version": "standalone-1.0",
echo   "created_at": "!date! !time!",
echo   "tool": "sems_standalone_backup.bat",
echo   "include_uploads": !SEMS_INCLUDE_UPLOADS!,
echo   "include_env": !SEMS_INCLUDE_ENV!,
echo   "backend_dir": "!SEMS_BACKEND_DIR:\=\\!"
echo }
) > "!MANIFEST!"

where py >nul 2>nul
if !ERRORLEVEL! EQU 0 (
    echo [INFO] 使用 py 打包
    py -3 -c "import zipfile, pathlib, json; r=pathlib.Path(r'!PACK_DIR!'); z=zipfile.ZipFile(r'!TMP_ROOT!\!ZIP_NAME!','w',zipfile.ZIP_DEFLATED,6); [z.write(p, p.relative_to(r).as_posix()) for p in r.rglob('*') if p.is_file()]; z.close(); print('OK', len(z.namelist()))"
) else (
    where powershell >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo [INFO] 使用 PowerShell Compress-Archive 打包
        powershell -NoProfile -Command "Compress-Archive -Path '!PACK_DIR!\*' -DestinationPath '!TMP_ROOT!\!ZIP_NAME!' -Force"
    ) else (
        echo [ERROR] 既没有 py 也没有 PowerShell，无法打包。
        popd
        exit /B 3
    )
)

if NOT EXIST "!TMP_ROOT!\!ZIP_NAME!" (
    echo [ERROR] 打包失败，目标 zip 不存在。
    popd
    exit /B 3
)

move /Y "!TMP_ROOT!\!ZIP_NAME!" "!ZIP_PATH!" >nul
echo [OK] 备份文件写入: !ZIP_PATH!

REM ---------------------------------------------------------------------
REM 3) openssl 加密（可选）
REM ---------------------------------------------------------------------
if NOT "!SEMS_ENC_PASSWORD!"=="" (
    where openssl >nul 2>nul
    if !ERRORLEVEL! NEQ 0 (
        echo [WARN] 未找到 openssl.exe，跳过加密
    ) else (
        openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -in "!ZIP_PATH!" -out "!ZIP_PATH!.enc" -pass pass:!SEMS_ENC_PASSWORD!
        if !ERRORLEVEL! EQU 0 (echo [OK] 加密副本：!ZIP_PATH!.enc) else (del /F "!ZIP_PATH!.enc" 2>nul & echo [ERROR] openssl 加密失败)
    )
)

REM ---------------------------------------------------------------------
REM 4) 复制到异地（SMB/共享盘/另一台电脑共享目录）
REM    Windows UNC 路径：\\server\share\sems_backups  直接可用
REM ---------------------------------------------------------------------
if NOT "!SEMS_SECONDARY_DIR!"=="" (
    if NOT EXIST "!SEMS_SECONDARY_DIR!" (
        echo [WARN] 异地目录 !SEMS_SECONDARY_DIR! 不存在/不可达，跳过
    ) else (
        set "COPIED="
        if EXIST "!ZIP_PATH!.enc" (
            copy /Y "!ZIP_PATH!.enc" "!SEMS_SECONDARY_DIR!\" >nul
            if !ERRORLEVEL! EQU 0 (set COPIED=1 & echo [OK] 加密副本复制到异地)
        )
        if NOT DEFINED COPIED (
            copy /Y "!ZIP_PATH!" "!SEMS_SECONDARY_DIR!\" >nul
            if !ERRORLEVEL! EQU 0 (echo [OK] zip 副本复制到异地) else (echo [ERROR] 异地复制失败)
        )
    )
)

REM ---------------------------------------------------------------------
REM 5) 清理旧备份（按最后修改时间倒序，保留前 N 个）
REM ---------------------------------------------------------------------
call :CLEANUP_DIR "!SEMS_PRIMARY_DIR!" !SEMS_KEEP_LOCAL!
if NOT "!SEMS_SECONDARY_DIR!"=="" if EXIST "!SEMS_SECONDARY_DIR!" call :CLEANUP_DIR "!SEMS_SECONDARY_DIR!" !SEMS_KEEP_SECONDARY!

echo [%date% %time%] ==== 独立备份完成 ====
popd
exit /B 0

REM ---------------------------------------------------------------------
REM 子函数：清理指定目录下 sems_standalone_*.zip(.enc)，只留 %2 个
REM ---------------------------------------------------------------------
:CLEANUP_DIR
set "D=%~1"
set "K=%~2"
if "!K!"=="0" exit /B 0
set /A i=0
for /F "delims=" %%F in ('dir /B /O-D /A-D "!D!\sems_standalone_*.zip*" 2^>nul') do (
    set /A i+=1
    if !i! GTR !K! (
        del /F "!D!\%%F" 2>nul
        if !ERRORLEVEL! EQU 0 (echo [CLEAN] 清理旧备份: !D!\%%F) else (echo [WARN] 清理失败: !D!\%%F)
    )
)
exit /B 0
