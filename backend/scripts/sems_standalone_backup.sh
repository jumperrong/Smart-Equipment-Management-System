#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# sems_standalone_backup.sh
# 系统级独立备份脚本（不依赖 FastAPI 服务进程是否运行）。
# 用于：crontab 定时任务；服务异常停机后应急备份；运维旁路灾备。
#
# 特点（低成本局域网 3-2-1 策略）：
#   1. 用 sqlite3 .backup API 生成一致性数据库快照（避免 WAL/SHM 不一致）
#   2. 打包：app.db + uploads/ + .env → 带时间戳 .zip
#   3. 可选副本：复制到 BACKUP_SECONDARY_DIR（NAS/SMB/U盘 挂载目录）
#   4. 可选加密：调用 openssl aes-256-cbc（绝大多数机器自带，不依赖 Python cryptography）
#   5. 按保留份数自动清理本地 / 异地
#
# 用法：
#   ./sems_standalone_backup.sh [config_file]
# 环境变量（可在 config_file 中覆盖，每行 KEY=VALUE）：
#   SEMS_BACKEND_DIR=/path/to/backend                 # 必需：backend 根目录（含 .env 与 data/）
#   SEMS_PRIMARY_DIR=/path/to/local_backups           # 默认：$SEMS_BACKEND_DIR/data/backups/standalone
#   SEMS_SECONDARY_DIR=                               # 可选：异地副本目录（绝对路径，例如 /mnt/nas/sems）
#   SEMS_ENC_PASSWORD=                                # 可选：非空则用 openssl aes-256-cbc 加密 zip，生成 .enc
#   SEMS_KEEP_LOCAL=30                                # 本地保留份数（0=不限制）
#   SEMS_KEEP_SECONDARY=14                            # 异地保留份数（0=不限制）
#   SEMS_INCLUDE_UPLOADS=1                            # 是否包含 uploads/
#   SEMS_INCLUDE_ENV=1                                # 是否包含 .env
#
# Crontab 例子（每天 02:15 执行，日志追加）：
#   15 2 * * * /opt/sems/scripts/sems_standalone_backup.sh >> /var/log/sems_backup.log 2>&1
# ------------------------------------------------------------------------------
set -u

# ---------- 默认配置 ----------
SEMS_BACKEND_DIR="${SEMS_BACKEND_DIR:-}"
SEMS_PRIMARY_DIR="${SEMS_PRIMARY_DIR:-}"
SEMS_SECONDARY_DIR="${SEMS_SECONDARY_DIR:-}"
SEMS_ENC_PASSWORD="${SEMS_ENC_PASSWORD:-}"
SEMS_KEEP_LOCAL="${SEMS_KEEP_LOCAL:-30}"
SEMS_KEEP_SECONDARY="${SEMS_KEEP_SECONDARY:-14}"
SEMS_INCLUDE_UPLOADS="${SEMS_INCLUDE_UPLOADS:-1}"
SEMS_INCLUDE_ENV="${SEMS_INCLUDE_ENV:-1}"

# 如果传入参数，则视为 config 文件（source）
if [[ $# -ge 1 && -f "$1" ]]; then
    # shellcheck disable=SC1090
    source "$1"
fi

# ---------- 必需：backend 目录 ----------
if [[ -z "$SEMS_BACKEND_DIR" ]]; then
    # 自探测：脚本所在目录推断，若脚本在 backend/scripts/ 则 ..
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$SCRIPT_DIR/../.env" && -d "$SCRIPT_DIR/../data" ]]; then
        SEMS_BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
        echo "[INFO] auto detect SEMS_BACKEND_DIR=$SEMS_BACKEND_DIR"
    else
        echo "[ERROR] SEMS_BACKEND_DIR 未设置，也无法从脚本目录 $SCRIPT_DIR 自动探测。请在环境变量或配置文件中设置。" >&2
        exit 2
    fi
fi
if [[ ! -d "$SEMS_BACKEND_DIR" ]]; then
    echo "[ERROR] SEMS_BACKEND_DIR=$SEMS_BACKEND_DIR 不存在" >&2
    exit 2
fi

cd "$SEMS_BACKEND_DIR" || exit 2

# ---------- 目录 ----------
DATA_DIR="$SEMS_BACKEND_DIR/data"
DB_FILE="$DATA_DIR/app.db"
UPLOADS_DIR="$DATA_DIR/uploads"
ENV_FILE="$SEMS_BACKEND_DIR/.env"
if [[ -z "$SEMS_PRIMARY_DIR" ]]; then
    SEMS_PRIMARY_DIR="$DATA_DIR/backups/standalone"
fi
mkdir -p "$SEMS_PRIMARY_DIR"

# ---------- 时间戳 & 临时工作目录 ----------
TS="$(date +%Y%m%d_%H%M%S)"
TMP_ROOT="$(mktemp -d -t sems_backup.XXXXXX)"
ZIP_NAME="sems_standalone_${TS}.zip"
ZIP_PATH="$SEMS_PRIMARY_DIR/$ZIP_NAME"
cleanup_tmp() {
    rm -rf "$TMP_ROOT"
}
trap cleanup_tmp EXIT

log() {
    echo "[$(date '+%F %T')] $*"
}

log "==== 开始独立备份 ts=$TS ===="
log "backend=$SEMS_BACKEND_DIR"
log "primary=$SEMS_PRIMARY_DIR"
[[ -n "$SEMS_SECONDARY_DIR" ]] && log "secondary=$SEMS_SECONDARY_DIR" || log "secondary=(未启用)"
[[ -n "$SEMS_ENC_PASSWORD" ]] && log "encryption=enabled(openssl aes-256-cbc)" || log "encryption=disabled"

# ---------- 1) SQLite 一致性快照 ----------
DB_SNAP="$TMP_ROOT/app.db"
if [[ -f "$DB_FILE" ]]; then
    if command -v sqlite3 >/dev/null 2>&1; then
        # sqlite3 .backup 官方 API：热备份一致性
        sqlite3 "$DB_FILE" ".backup '$DB_SNAP'"
        RC=$?
        if [[ $RC -ne 0 ]]; then
            log "[WARN] sqlite3 .backup 返回 $RC，改用直接文件拷贝（服务未运行时是安全的）"
            cp -f "$DB_FILE" "$DB_SNAP" 2>/dev/null || true
            # 同时带 WAL/SHM（如果有）
            cp -f "${DB_FILE}-wal" "${DB_SNAP}-wal" 2>/dev/null || true
            cp -f "${DB_FILE}-shm" "${DB_SNAP}-shm" 2>/dev/null || true
        else
            log "[OK] sqlite3 backup API 生成快照成功 $(wc -c <"$DB_SNAP" | tr -d ' ') bytes"
        fi
    else
        log "[WARN] 系统没装 sqlite3 命令，改用文件直拷贝；建议 apt install sqlite3 / yum install sqlite 以支持热备份一致性"
        cp -f "$DB_FILE" "$DB_SNAP" 2>/dev/null || true
        cp -f "${DB_FILE}-wal" "${DB_SNAP}-wal" 2>/dev/null || true
        cp -f "${DB_FILE}-shm" "${DB_SNAP}-shm" 2>/dev/null || true
    fi
else
    log "[WARN] 数据库文件不存在：$DB_FILE（全新环境）"
fi

# ---------- 2) 打包 zip ----------
ZIP_TMP="$TMP_ROOT/$ZIP_NAME"
MANIFEST="$TMP_ROOT/_backup_manifest.json"
cat >"$MANIFEST" <<EOF
{
  "version": "standalone-1.0",
  "created_at": "$(date -Iseconds)",
  "tool": "sems_standalone_backup.sh",
  "include_uploads": ${SEMS_INCLUDE_UPLOADS},
  "include_env": ${SEMS_INCLUDE_ENV},
  "backend_dir": "$SEMS_BACKEND_DIR",
  "items": {}
}
EOF

# 用 Python zip 更稳（绝大多数 Linux 自带 python3；也可回退 zip 命令）
pack_with_python() {
    python3 - "$@" <<'PY'
import sys, os, zipfile, json, pathlib
tmp_root, db_snap, uploads_dir, env_file, zip_out, manifest_in, include_uploads, include_env = sys.argv[1:9]
include_uploads = include_uploads == "1"
include_env = include_env == "1"
with open(manifest_in, "r", encoding="utf-8") as f:
    m = json.load(f)
items = m.setdefault("items", {})
with zipfile.ZipFile(zip_out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    db = pathlib.Path(db_snap)
    if db.exists() and db.stat().st_size > 0:
        zf.write(db, "app.db")
        items["db"] = {"name": "app.db", "size": db.stat().st_size}
        for ext in ("-wal", "-shm"):
            side = db.with_name(db.name + ext)
            if side.exists():
                zf.write(side, "app.db" + ext)
    if include_uploads:
        up = pathlib.Path(uploads_dir)
        if up.exists() and up.is_dir():
            files = sorted([p for p in up.rglob("*") if p.is_file()])
            if files:
                for p in files:
                    rel = p.relative_to(up).as_posix()
                    zf.write(p, "uploads/" + rel)
                items["uploads"] = {"count": len(files), "total_size": sum(p.stat().st_size for p in files)}
    if include_env:
        env = pathlib.Path(env_file)
        if env.exists():
            zf.write(env, ".env")
            items["env"] = {"name": ".env", "size": env.stat().st_size}
    # 最后写 manifest（覆盖掉空版本，带上 items）
    zf.writestr("_backup_manifest.json", json.dumps(m, ensure_ascii=False, indent=2))
print("OK: zip=" + zip_out + " items=" + json.dumps(items, ensure_ascii=False))
PY
}

if command -v python3 >/dev/null 2>&1; then
    OUT=$(pack_with_python \
        "$TMP_ROOT" "$DB_SNAP" "$UPLOADS_DIR" "$ENV_FILE" "$ZIP_TMP" "$MANIFEST" \
        "$SEMS_INCLUDE_UPLOADS" "$SEMS_INCLUDE_ENV" 2>&1)
    RC=$?
    if [[ $RC -eq 0 && -f "$ZIP_TMP" ]]; then
        log "[OK] python3 打包完成：$OUT"
    else
        log "[ERROR] python3 打包失败：$OUT"
        exit 3
    fi
else
    log "[WARN] 没有 python3，使用 zip 命令（可能缺少压缩率与 manifest）"
    if ! command -v zip >/dev/null 2>&1; then
        log "[ERROR] 既无 python3 也无 zip 命令，请至少装其一" >&2
        exit 3
    fi
    (
        cd "$TMP_ROOT" || exit 1
        cp "$MANIFEST" ./_backup_manifest.json
        zip -q -9 "$ZIP_TMP" _backup_manifest.json
        [[ -f "$DB_SNAP" ]] && zip -q -9 "$ZIP_TMP" app.db
        if [[ "$SEMS_INCLUDE_UPLOADS" == "1" && -d "$UPLOADS_DIR" ]]; then
            zip -q -r -9 "$ZIP_TMP" uploads -i "$UPLOADS_DIR/*" >/dev/null 2>&1 || true
        fi
        if [[ "$SEMS_INCLUDE_ENV" == "1" && -f "$ENV_FILE" ]]; then
            cp "$ENV_FILE" .env && zip -q -9 "$ZIP_TMP" .env
        fi
    )
fi

# 原子搬移到 primary 目录
mv -f "$ZIP_TMP" "$ZIP_PATH"
SIZE=$(wc -c <"$ZIP_PATH" | tr -d ' ')
log "[OK] 备份文件写入 primary：$ZIP_PATH ($SIZE bytes)"

# ---------- 3) 可选 openssl 加密（局域网 SMB/NAS 可防闲杂人直接打开） ----------
if [[ -n "$SEMS_ENC_PASSWORD" ]]; then
    if ! command -v openssl >/dev/null 2>&1; then
        log "[WARN] 未安装 openssl，跳过加密"
    else
        ENC_PATH="${ZIP_PATH}.enc"
        # PBKDF2 + salt + AES-256-CBC（openssl 1.1+ 都支持 -pbkdf2）
        openssl enc -aes-256-cbc -pbkdf2 -iter 200000 \
            -salt \
            -in "$ZIP_PATH" \
            -out "$ENC_PATH" \
            -pass "pass:$SEMS_ENC_PASSWORD"
        RC=$?
        if [[ $RC -eq 0 && -f "$ENC_PATH" ]]; then
            log "[OK] 加密副本：$ENC_PATH ($(wc -c <"$ENC_PATH" | tr -d ' ') bytes)"
        else
            log "[ERROR] openssl 加密失败 RC=$RC"
            rm -f "$ENC_PATH"
        fi
    fi
fi

# ---------- 4) 可选副本到异地目录 ----------
copy_to_dir() {
    local src="$1" dst_dir="$2"
    [[ -z "$dst_dir" || ! -d "$dst_dir" ]] && return 1
    local dst="$dst_dir/$(basename "$src")"
    cp -f "$src" "$dst"
    # 写后大小一致
    local s1 s2
    s1=$(wc -c <"$src" | tr -d ' ')
    s2=$(wc -c <"$dst" | tr -d ' ')
    [[ "$s1" == "$s2" ]]
}

if [[ -n "$SEMS_SECONDARY_DIR" ]]; then
    if [[ ! -d "$SEMS_SECONDARY_DIR" ]]; then
        log "[WARN] SECONDARY_DIR 不存在/不可访问：$SEMS_SECONDARY_DIR，跳过异地副本"
    else
        # 优先复制加密文件
        COPIED=0
        if [[ -n "$SEMS_ENC_PASSWORD" && -f "${ZIP_PATH}.enc" ]]; then
            if copy_to_dir "${ZIP_PATH}.enc" "$SEMS_SECONDARY_DIR"; then
                log "[OK] 加密副本复制到异地：$SEMS_SECONDARY_DIR/${ZIP_NAME}.enc"
                COPIED=1
            else
                log "[WARN] 异地复制加密文件失败，改试 zip"
            fi
        fi
        if [[ $COPIED -eq 0 ]]; then
            if copy_to_dir "$ZIP_PATH" "$SEMS_SECONDARY_DIR"; then
                log "[OK] zip 副本复制到异地：$SEMS_SECONDARY_DIR/$ZIP_NAME"
            else
                log "[ERROR] 异地复制失败"
            fi
        fi
    fi
fi

# ---------- 5) 清理本地 / 异地旧备份 ----------
cleanup_dir() {
    local dir="$1" keep="$2" pattern="$3"
    [[ ! -d "$dir" ]] && return 0
    [[ "$keep" == "0" ]] && return 0
    # 列出匹配 pattern 的文件按修改时间倒序，N+1 起删除
    local files i=0
    files=$(ls -1t "$dir" 2>/dev/null | grep -E "$pattern" || true)
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        i=$((i + 1))
        if [[ $i -gt $keep ]]; then
            if rm -f "$dir/$f"; then
                log "[CLEAN] 清理旧备份：$dir/$f"
            else
                log "[WARN] 清理失败：$dir/$f"
            fi
        fi
    done <<<"$files"
}

cleanup_dir "$SEMS_PRIMARY_DIR" "$SEMS_KEEP_LOCAL" '^sems_standalone_[0-9_]+\.zip(\.enc)?$'
if [[ -n "$SEMS_SECONDARY_DIR" && -d "$SEMS_SECONDARY_DIR" ]]; then
    cleanup_dir "$SEMS_SECONDARY_DIR" "$SEMS_KEEP_SECONDARY" '^sems_standalone_[0-9_]+\.zip(\.enc)?$'
fi

log "==== 独立备份完成 ===="
exit 0
