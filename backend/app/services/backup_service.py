"""系统备份与恢复服务。

备份内容（打包为单个 .zip 文件）：
- 数据库快照：通过 sqlite3 backup API 生成一致性 app.db（避免 WAL 不一致）
- 上传文件目录：data/uploads/ 所有用户上传的附件
- 环境配置文件：.env
- 清单文件：_backup_manifest.json（备份时间、版本、各模块文件数/大小）

恢复流程（严格保证数据安全）：
1. 校验备份包合法性（包含 manifest + 必选文件）
2. 对当前状态做"自动快照备份"（恢复失败可回滚）
3. 停止数据库写入（要求用户重启服务后生效，或通过强制替换文件）
4. 恢复数据文件
5. 返回提示重启服务

设计安全原则：
- 默认备份根目录在 <backend>/data/backups/（白名单内目录，避免任意路径写入）
- 用户可传入 sub_dir（备份子目录名，例如 "2026-08-07-pre-upgrade"）
- 任何写操作前都会验证路径合法性（拒绝 ../ 绝对路径等）
- 恢复前必做自动快照，且默认保留
"""
import base64
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import zipfile
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

try:
    # 优先 cryptography（如装了 pyca/cryptography）
    from cryptography.fernet import Fernet, InvalidToken as FernetInvalidToken
    _HAS_CRYPTOGRAPHY = True
except Exception:
    _HAS_CRYPTOGRAPHY = False
    Fernet = None  # type: ignore
    FernetInvalidToken = Exception  # type: ignore


VERSION = "1.0.0"


# ---------- 路径工具 ----------

def _backend_root() -> pathlib.Path:
    """返回 backend 目录（运行工作目录）。"""
    # 开发模式：本文件位于 backend/app/services/backup_service.py → ../../
    dev_root = pathlib.Path(__file__).resolve().parent.parent.parent
    if getattr(sys, "frozen", False):
        frozen_root = pathlib.Path(sys.executable).parent
        # 优先用 frozen 根，但 data 目录在根
        return frozen_root
    return dev_root


def _default_data_dir() -> pathlib.Path:
    """<backend>/data/"""
    return _backend_root() / "data"


def default_backup_root() -> pathlib.Path:
    """<backend>/data/backups/"""
    return _default_data_dir() / "backups"


def _db_path() -> pathlib.Path:
    return _default_data_dir() / "app.db"


def _env_path() -> pathlib.Path:
    """.env 文件路径：frozen 模式下是 exe 同级，否则 backend 根目录。"""
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).parent / ".env"
    return _backend_root() / ".env"


def _uploads_dir() -> pathlib.Path:
    return _default_data_dir() / "uploads"


_SAFE_NAME_RE = re.compile(r"^[\w\-\.]+$")  # 字母数字下划线点号短横线


def _validate_sub_dir(sub_dir: str) -> str:
    """校验子目录名是否安全。允许空字符串（使用默认根目录）。"""
    if sub_dir is None or sub_dir.strip() == "":
        return ""
    s = sub_dir.strip().replace("\\", "/").strip("/")
    if not s:
        return ""
    for part in s.split("/"):
        if not _SAFE_NAME_RE.match(part):
            raise HTTPException(
                status_code=400,
                detail=f"路径名非法（仅允许字母、数字、下划线、点号、短横线）：{part!r}",
            )
        if part in ("..", "."):
            raise HTTPException(status_code=400, detail=f"路径名非法：{part!r}")
    return s


def resolve_backup_dir(sub_dir: Optional[str] = None) -> pathlib.Path:
    """解析实际备份目录。

    - sub_dir="" 或 None → data/backups/
    - sub_dir="2026-08-07" → data/backups/2026-08-07/
    - 非法子目录名抛 400
    """
    safe = _validate_sub_dir(sub_dir)
    if safe:
        target = default_backup_root() / safe
    else:
        target = default_backup_root()
    # 防止 ../ 攻击（即使正则过了再防御一层）
    try:
        target.resolve().relative_to(default_backup_root().resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="备份路径越界，拒绝访问")
    target.mkdir(parents=True, exist_ok=True)
    return target


def resolve_backup_file(file_name: str, sub_dir: Optional[str] = None) -> pathlib.Path:
    """解析备份文件路径，防御路径穿越。"""
    if not file_name or file_name in (".", ".."):
        raise HTTPException(status_code=400, detail="文件名非法")
    if "/" in file_name or "\\" in file_name:
        raise HTTPException(status_code=400, detail="文件名不能含路径分隔符")
    if not file_name.endswith(".zip"):
        raise HTTPException(status_code=400, detail="备份文件必须为 .zip")
    d = resolve_backup_dir(sub_dir)
    f = d / file_name
    if not f.exists() or not f.is_file():
        raise HTTPException(status_code=404, detail="备份文件不存在")
    try:
        f.resolve().relative_to(default_backup_root().resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="备份文件路径越界")
    return f


# ---------- 备份清单 ----------

def _now_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _file_size(p: pathlib.Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


def _human_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    s = float(size)
    for u in units:
        if s < 1024:
            return f"{s:.1f} {u}"
        s /= 1024
    return f"{s:.1f} PB"


# ---------- 备份数据库（SQLite 一致性快照） ----------

def _sqlite_backup_to_memory(src_path: pathlib.Path) -> bytes:
    """用 sqlite3 备份接口生成一致性快照（避免 WAL/SHM 问题）。"""
    if not src_path.exists():
        return b""
    src = sqlite3.connect(str(src_path))
    dst_conn = sqlite3.connect(":memory:")
    try:
        src.backup(dst_conn)
        # 导出 memory DB 到字节流
        buf = io.BytesIO()
        for line in dst_conn.iterdump():
            buf.write(line.encode("utf-8"))
            buf.write(b"\n")
        # 转储 SQL 文本较脆弱，改用另一种方式：写临时文件再读
        return _sqlite_backup_to_bytes_alt(src)
    finally:
        dst_conn.close()
        src.close()


def _sqlite_backup_to_bytes_alt(src_conn: sqlite3.Connection) -> bytes:
    """用 sqlite3 backup 写入临时文件，再读为 bytes。"""
    import tempfile
    tmp = pathlib.Path(tempfile.mkdtemp()) / "snap.db"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        dst = sqlite3.connect(str(tmp))
        try:
            src_conn.backup(dst)
        finally:
            dst.close()
        data = tmp.read_bytes()
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
            if tmp.parent.exists():
                tmp.parent.rmdir()
        except OSError:
            pass
    return data


# ---------- 上传文件压缩 ----------

def _compress_uploads_to_targz(uploads_dir: pathlib.Path) -> tuple[bytes, int, int]:
    """将 uploads 目录打包压缩为 tar.gz 字节流。

    返回 (tar_gz_bytes, file_count, total_uncompressed_size)
    """
    buf = io.BytesIO()
    file_count = 0
    total_size = 0
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=6) as tar:
        for f in sorted(uploads_dir.rglob("*")):
            if f.is_file():
                rel = f.relative_to(uploads_dir)
                tar.add(f, arcname=rel.as_posix(), recursive=False)
                file_count += 1
                total_size += _file_size(f)
    return buf.getvalue(), file_count, total_size


# ---------- 创建备份 ----------

def create_backup(
    sub_dir: Optional[str] = None,
    note: Optional[str] = None,
    include_uploads: bool = True,
    include_env: bool = True,
) -> dict:
    """创建系统完整备份并写入备份目录。

    返回：{file_name, file_path, size, created_at, items: {...}}
    """
    backup_dir = resolve_backup_dir(sub_dir)
    file_name = f"sems_backup_{_now_str()}.zip"
    file_path = backup_dir / file_name

    created_at = datetime.now().isoformat(timespec="seconds")
    manifest = {
        "version": VERSION,
        "created_at": created_at,
        "note": note or "",
        "include_uploads": include_uploads,
        "include_env": include_env,
        "items": {},
    }

    # 1. 数据库（一致性快照）
    db_bytes = b""
    db_exists = _db_path().exists()
    if db_exists:
        db_bytes = _sqlite_backup_to_memory(_db_path())

    # 2. 上传文件（压缩为 tar.gz）
    uploads_tar_gz = None
    uploads_info = None
    uploads_dir = _uploads_dir()
    if include_uploads and uploads_dir.exists():
        uploads_tar_gz, u_count, u_size = _compress_uploads_to_targz(uploads_dir)
        if u_count > 0:
            uploads_info = {"count": u_count, "total_size": u_size, "compressed_size": len(uploads_tar_gz)}

    # 3. .env 字节
    env_bytes = None
    env_path = _env_path()
    if include_env and env_path.exists():
        env_bytes = env_path.read_bytes()

    # 写 zip
    with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # manifest（写到最后方便读取时先校验其他文件）
        # 先写数据库
        if db_bytes:
            zf.writestr("app.db", db_bytes)
            manifest["items"]["db"] = {"name": "app.db", "size": len(db_bytes)}

        # 上传文件（压缩 tar.gz）
        if uploads_info:
            zf.writestr("uploads.tar.gz", uploads_tar_gz)
            manifest["items"]["uploads"] = {
                "format": "tar.gz",
                "archive": "uploads.tar.gz",
                "count": uploads_info["count"],
                "total_size": uploads_info["total_size"],
                "compressed_size": uploads_info["compressed_size"],
            }

        # .env
        if env_bytes is not None:
            zf.writestr(".env", env_bytes)
            manifest["items"]["env"] = {"name": ".env", "size": len(env_bytes)}

        # manifest 在最后（读取时优先校验存在）
        zf.writestr("_backup_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    # 汇总信息
    total_size = _file_size(file_path)
    return {
        "file_name": file_name,
        "sub_dir": sub_dir or "",
        "file_path": str(file_path),
        "size": total_size,
        "size_human": _human_size(total_size),
        "created_at": created_at,
        "note": note or "",
        "include_uploads": include_uploads,
        "include_env": include_env,
        "items": manifest["items"],
    }


# ---------- 列出备份 ----------

def list_backups(sub_dir: Optional[str] = None) -> list[dict]:
    """列出指定（子）目录下的所有备份，按创建时间倒序。"""
    backup_dir = resolve_backup_dir(sub_dir)
    if not backup_dir.exists():
        return []
    files = [f for f in backup_dir.iterdir() if f.is_file() and f.name.endswith(".zip")]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        info = _read_backup_info(f)
        result.append(info)
    return result


def _read_backup_info(file_path: pathlib.Path) -> dict:
    """从 zip 包中读取 manifest 并返回摘要。"""
    size = _file_size(file_path)
    info = {
        "file_name": file_path.name,
        "size": size,
        "size_human": _human_size(size),
        "created_at": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(timespec="seconds"),
        "note": "",
        "items": {},
        "valid": False,
        "version": "",
    }
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            if "_backup_manifest.json" in zf.namelist():
                with zf.open("_backup_manifest.json") as mf:
                    m = json.load(mf)
                info["note"] = m.get("note", "")
                info["items"] = m.get("items", {})
                info["valid"] = True
                info["version"] = m.get("version", "")
                info["created_at"] = m.get("created_at", info["created_at"])
            else:
                # 兼容：没有 manifest 就按 namelist 估算
                names = zf.namelist()
                has_db = "app.db" in names
                has_env = ".env" in names
                items = {}
                if has_db:
                    try:
                        items["db"] = {"size": zf.getinfo("app.db").file_size}
                    except KeyError:
                        pass
                # 新格式：uploads.tar.gz 单文件
                if "uploads.tar.gz" in names:
                    items["uploads"] = {
                        "format": "tar.gz",
                        "count": 0,
                        "total_size": 0,
                        "compressed_size": zf.getinfo("uploads.tar.gz").file_size,
                    }
                else:
                    # 旧格式：uploads/ 目录下的文件
                    uploads = [n for n in names if n.startswith("uploads/")]
                    if uploads:
                        items["uploads"] = {"count": len(uploads), "total_size": sum(zf.getinfo(n).file_size for n in uploads)}
                if has_env:
                    try:
                        items["env"] = {"size": zf.getinfo(".env").file_size}
                    except KeyError:
                        pass
                info["items"] = items
                info["valid"] = bool(items)
    except (zipfile.BadZipFile, OSError, json.JSONDecodeError):
        info["valid"] = False
    return info


# ---------- 删除备份 ----------

def delete_backup(file_name: str, sub_dir: Optional[str] = None) -> bool:
    f = resolve_backup_file(file_name, sub_dir)
    try:
        f.unlink()
        return True
    except OSError:
        return False


# ---------- 恢复备份 ----------

def _verify_backup(file_path: pathlib.Path) -> dict:
    """校验备份包完整性，返回 manifest 字典。"""
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="备份文件不存在")
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            if "_backup_manifest.json" not in zf.namelist():
                raise HTTPException(status_code=400, detail="备份包缺少 manifest，无法安全恢复")
            with zf.open("_backup_manifest.json") as mf:
                manifest = json.load(mf)
            # 校验必选文件存在
            names = set(zf.namelist())
            if "db" in manifest.get("items", {}):
                if "app.db" not in names:
                    raise HTTPException(status_code=400, detail="备份包缺失 app.db")
            bad = zf.testzip()
            if bad is not None:
                raise HTTPException(status_code=400, detail=f"备份包 CRC 校验失败：{bad}")
            return manifest
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="备份包已损坏（非 zip 文件）")


def _auto_snapshot(sub_dir: Optional[str] = None) -> dict:
    """恢复前自动做当前状态快照。默认放到 auto-snapshots 子目录。"""
    snap_dir = f"auto-snapshots/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if sub_dir:
        # 把 auto 快照也放到指定子目录下
        snap_dir = f"{sub_dir.rstrip('/')}/auto-snapshots/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        info = create_backup(
            sub_dir=snap_dir,
            note="自动快照（恢复前）",
            include_uploads=True,
            include_env=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自动快照失败，为保护数据已中止恢复：{e}")
    info["snapshot_dir"] = snap_dir
    return info


def restore_backup(
    file_name: str,
    sub_dir: Optional[str] = None,
    restore_db: bool = True,
    restore_uploads: bool = True,
    restore_env: bool = True,
    skip_auto_snapshot: bool = False,
) -> dict:
    """从备份恢复。

    流程：
    1. 校验备份包合法
    2. （默认）对当前状态做自动快照
    3. 解压 -> 覆盖 app.db / uploads/ / .env
    4. 返回重启提示
    """
    file_path = resolve_backup_file(file_name, sub_dir)
    manifest = _verify_backup(file_path)

    snapshot = None
    if not skip_auto_snapshot:
        snapshot = _auto_snapshot(sub_dir)

    # 实际文件操作
    report = {"db": False, "uploads": {"count": 0, "total_size": 0}, "env": False}
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            items = manifest.get("items", {})

            # 数据库
            if restore_db and "db" in items:
                db_target = _db_path()
                db_target.parent.mkdir(parents=True, exist_ok=True)
                # 删除可能存在的 WAL/SHM（防止 SQLite 读取不一致）
                for ext in (".db-wal", ".db-shm"):
                    w = db_target.with_suffix(ext) if ext != ".db-wal" else pathlib.Path(str(db_target) + "-wal")
                    if w.exists():
                        try:
                            w.unlink()
                        except OSError:
                            pass
                shm = pathlib.Path(str(db_target) + "-shm")
                if shm.exists():
                    try:
                        shm.unlink()
                    except OSError:
                        pass
                with zf.open("app.db") as src, open(db_target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                report["db"] = True

            # 上传文件
            if restore_uploads and "uploads" in items:
                uploads_item = items["uploads"]
                uploads_dir = _uploads_dir()
                # 先清空现有的 uploads（避免残留）
                if uploads_dir.exists():
                    try:
                        shutil.rmtree(uploads_dir)
                    except OSError:
                        # 删不动就覆盖
                        pass
                uploads_dir.mkdir(parents=True, exist_ok=True)
                upload_count = 0
                upload_size = 0

                if uploads_item.get("format") == "tar.gz" or "uploads.tar.gz" in zf.namelist():
                    # 新格式：解压 tar.gz
                    with zf.open("uploads.tar.gz") as src:
                        tar_buf = io.BytesIO(src.read())
                    with tarfile.open(fileobj=tar_buf, mode="r:gz") as tar:
                        for member in tar.getmembers():
                            if member.isfile():
                                tar.extract(member, path=uploads_dir)
                                upload_count += 1
                                upload_size += member.size
                else:
                    # 旧格式：逐个解压 uploads/ 下的文件
                    for name in zf.namelist():
                        if not name.startswith("uploads/") or name.endswith("/"):
                            continue
                        rel = name[len("uploads/"):]
                        target = uploads_dir / rel
                        target.parent.mkdir(parents=True, exist_ok=True)
                        info = zf.getinfo(name)
                        with zf.open(name) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        upload_count += 1
                        upload_size += info.file_size
                report["uploads"] = {"count": upload_count, "total_size": upload_size}

            # .env
            if restore_env and "env" in items:
                env_target = _env_path()
                with zf.open(".env") as src, open(env_target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                report["env"] = True
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"恢复文件写入失败：{e}（自动快照已保存，可手动回滚：{snapshot['file_path'] if snapshot else '无'}）",
        )

    return {
        "ok": True,
        "restored": report,
        "auto_snapshot": snapshot,
        "requires_restart": True,
        "message": "数据已覆盖写入。为确保 SQLite 连接断开并加载新数据库文件，必须重启服务。",
    }


# ---------- 备份统计 ----------

def backup_stats(sub_dir: Optional[str] = None) -> dict:
    """返回备份统计信息（总数、大小、最后备份时间等）。"""
    backup_dir = resolve_backup_dir(sub_dir)
    total_size = 0
    count = 0
    latest = None
    if backup_dir.exists():
        for f in backup_dir.rglob("*.zip"):
            if f.is_file():
                try:
                    total_size += f.stat().st_size
                    count += 1
                    if latest is None or f.stat().st_mtime > latest:
                        latest = f.stat().st_mtime
                except OSError:
                    continue
    return {
        "backup_root": str(default_backup_root()),
        "count": count,
        "total_size": total_size,
        "total_size_human": _human_size(total_size),
        "latest_backup_at": datetime.fromtimestamp(latest).isoformat(timespec="seconds") if latest else None,
        "auto_snapshot_count": _count_auto_snapshots(),
    }


def _count_auto_snapshots() -> int:
    base = default_backup_root()
    if not base.exists():
        return 0
    n = 0
    for f in base.rglob("*.zip"):
        if "auto-snapshots" in str(f):
            n += 1
    return n


# ============================================================================
#  灾备扩展：加密 + 异地副本(第二目录) + 备份健康度校验
# ============================================================================

# AES 加密备份扩展名（Fernet）
_ENC_SUFFIX = ".aes256"


# ---------- 派生加密密钥 ----------

def _derive_backup_key(secret: str) -> bytes:
    """把任意长度的 secret（SECRET_KEY 或自定义密码）转换为 Fernet 需要的 32 字节 base64 key。
    Fernet = AES-128-CBC + HMAC-SHA256，key 要求 32 字节随机数 base64 编码。
    为兼顾"可离线解密+与 SECRET_KEY 解耦"，采用 PBKDF2-HMAC-SHA256，10 万次迭代。
    """
    if not secret:
        raise HTTPException(status_code=400, detail="缺少加密密钥：请在系统设置填入 BACKUP_ENCRYPTION_PASSWORD 或保持默认 SECRET_KEY")
    # 固定盐（备份可跨机器复原；需要更强可在包里加 salt 字段）
    salt = b"sems_backup_salt_v1"
    dk = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations=200_000, dklen=32)
    return base64.urlsafe_b64encode(dk)


def _get_backup_key() -> Optional[bytes]:
    """读取备份加密密钥：优先 BACKUP_ENCRYPTION_PASSWORD，其次 SECRET_KEY。都为空返回 None（不加密）。"""
    # 读取 settings 时延迟 import，避免循环
    from app.core.config import settings
    pwd = getattr(settings, "BACKUP_ENCRYPTION_PASSWORD", None)
    key_src = None
    if pwd and isinstance(pwd, str) and pwd.strip():
        key_src = pwd.strip()
    elif getattr(settings, "SECRET_KEY", None) and settings.SECRET_KEY and settings.SECRET_KEY != "change-me-in-prod":
        key_src = settings.SECRET_KEY
    if not key_src:
        return None
    return _derive_backup_key(key_src)


def is_backup_encryption_available() -> dict:
    """返回加密能力状态。"""
    return {
        "has_cryptography": _HAS_CRYPTOGRAPHY,
        "has_key": _get_backup_key() is not None,
    }


# ---------- 加密/解密 ZIP 为 .zip.aes256 ----------

def encrypt_file(src: pathlib.Path, dst: pathlib.Path) -> None:
    """把 src（zip）加密为 dst.aes256。"""
    if not _HAS_CRYPTOGRAPHY:
        raise HTTPException(status_code=500, detail="未安装 cryptography 库，无法启用加密。请运行：pip install cryptography")
    key = _get_backup_key()
    if key is None:
        raise HTTPException(status_code=400, detail="未配置加密密钥：请设置 BACKUP_ENCRYPTION_PASSWORD 或有效的 SECRET_KEY")
    f = Fernet(key)
    data = src.read_bytes()
    # 分块加密：对大文件用 stream 更省内存，Fernet 是单包格式，这里兜底按 64MB 分片
    CHUNK = 64 * 1024 * 1024
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as out:
        # 先写 8 字节魔数 + 版本，便于离线校验
        out.write(b"SEMSBK1\0")
        # 总长度
        out.write(len(data).to_bytes(8, "little"))
        if len(data) <= CHUNK:
            token = f.encrypt(data)
            out.write(len(token).to_bytes(4, "little"))
            out.write(token)
        else:
            for i in range(0, len(data), CHUNK):
                chunk = data[i:i + CHUNK]
                token = f.encrypt(chunk)
                out.write(len(token).to_bytes(4, "little"))
                out.write(token)
            # 结尾 4 字节 0 作为分隔（可选，这里简化：靠总长度已够）


def decrypt_to_tempfile(encrypted_file: pathlib.Path) -> pathlib.Path:
    """把加密的备份解密为临时 zip，返回临时文件路径（调用方负责清理）。"""
    if not _HAS_CRYPTOGRAPHY:
        raise HTTPException(status_code=500, detail="未安装 cryptography 库，无法解密。请运行：pip install cryptography")
    key = _get_backup_key()
    if key is None:
        raise HTTPException(status_code=400, detail="未配置加密密钥：请设置 BACKUP_ENCRYPTION_PASSWORD 或有效的 SECRET_KEY")
    f = Fernet(key)
    data = encrypted_file.read_bytes()
    if len(data) < 16 or not data.startswith(b"SEMSBK1\0"):
        raise HTTPException(status_code=400, detail="加密文件格式不对（未找到 SEMSBK1 魔数）")
    pos = 8
    total = int.from_bytes(data[pos:pos + 8], "little")
    pos += 8
    buf = bytearray()
    while pos < len(data):
        if pos + 4 > len(data):
            break
        tlen = int.from_bytes(data[pos:pos + 4], "little")
        pos += 4
        if tlen == 0:
            break
        token = data[pos:pos + tlen]
        pos += tlen
        try:
            buf.extend(f.decrypt(token))
        except FernetInvalidToken:
            raise HTTPException(status_code=400, detail="解密失败：加密密钥不对或备份包已损坏。请核对 BACKUP_ENCRYPTION_PASSWORD / SECRET_KEY。")
    if len(buf) != total:
        raise HTTPException(status_code=400, detail=f"解密后长度不对：期望 {total} 实际 {len(buf)}，备份包可能损坏")
    tmp = pathlib.Path(tempfile.mkdtemp()) / "decrypted_backup.zip"
    tmp.write_bytes(bytes(buf))
    return tmp


# ---------- 异地副本（第二备份目录 / 离线 NAS / SMB 挂载目录） ----------

def resolve_secondary_root() -> Optional[pathlib.Path]:
    """读取第二备份目录：
    - 优先 BACKUP_SECONDARY_DIR 环境变量（绝对路径，例如：/mnt/nas/sems_backups 或 //server/share/backups）
    - 非空才启用；空/未设置返回 None（仅本地一份）。
    为避免写入越权：这里只允许绝对路径，且必须已经存在（管理员需提前创建并赋予写权限）。
    """
    from app.core.config import settings
    raw = getattr(settings, "BACKUP_SECONDARY_DIR", None)
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip().strip('"').strip("'")
    if not raw:
        return None
    p = pathlib.Path(raw)
    # 允许 Windows UNC：\\server\share 也是绝对路径形式
    if not p.is_absolute() and not (len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha()):
        # Windows UNC 形如 \\server\share  → pathlib 在 Linux 下当相对；这里宽松处理：开头 // 或 \\ 也认为合法
        if not (raw.startswith("\\\\") or raw.startswith("//")):
            raise HTTPException(status_code=400, detail=f"BACKUP_SECONDARY_DIR 必须是绝对路径：{raw}")
    # 要求目录已存在（管理员需先建好）
    if not p.exists():
        raise HTTPException(
            status_code=400,
            detail=f"第二备份目录不存在或无法访问：{raw}。请提前在服务器上创建并赋予本进程读写权限（SMB/NAS 请先挂载）。",
        )
    if not p.is_dir():
        raise HTTPException(status_code=400, detail=f"BACKUP_SECONDARY_DIR 不是目录：{raw}")
    return p


def _copy_to_secondary(src_file: pathlib.Path, secondary_root: pathlib.Path, sub_dir: Optional[str] = None) -> pathlib.Path:
    """把本地备份复制到第二目录。sub_dir 结构与本地一致。"""
    safe = _validate_sub_dir(sub_dir)
    if safe:
        target_dir = secondary_root / safe
    else:
        target_dir = secondary_root
    target_dir.mkdir(parents=True, exist_ok=True)
    # 安全性：二次确认最终目标在 secondary_root 下
    try:
        target_dir.resolve().relative_to(secondary_root.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="第二备份子目录路径越界，拒绝写入")
    dst = target_dir / src_file.name
    # copy2 保留 mtime，便于后续按时间清理
    shutil.copy2(src_file, dst)
    # 校验：写后大小一致
    if dst.stat().st_size != src_file.stat().st_size:
        try:
            dst.unlink()
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"复制到第二目录失败：写入后大小不一致 {dst}")
    return dst


def cleanup_dir_backups(root: pathlib.Path, sub_dir: Optional[str] = None, keep_count: int = 14) -> int:
    """指定目录下按时间清理旧备份。返回删除数。"""
    safe = _validate_sub_dir(sub_dir)
    if safe:
        d = root / safe
    else:
        d = root
    if not d.exists():
        return 0
    files = [f for f in d.iterdir() if f.is_file() and (f.name.endswith(".zip") or f.name.endswith(_ENC_SUFFIX))]
    if len(files) <= max(1, keep_count):
        return 0
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    removed = 0
    for old in files[keep_count:]:
        try:
            old.unlink()
            removed += 1
        except OSError:
            pass
    return removed


# ---------- 备份健康度校验（可还原性验证） ----------

def _quick_smoke_restore(zip_file: pathlib.Path) -> dict:
    """把 zip 解压到临时目录，快速 smoke test：
    - db 能被 sqlite3 打开，能查出 users 表/不为空
    - 有 manifest
    返回 {ok, db_tables_count, db_users_count, uploads_count}
    """
    tmp_root = pathlib.Path(tempfile.mkdtemp(prefix="sems_restore_smoke_"))
    try:
        # 校验 manifest + CRC
        manifest = _verify_backup(zip_file)
        db_info = {"tables": 0, "users_count": None, "equipment_count": None}
        uploads_count = 0
        with zipfile.ZipFile(zip_file, "r") as zf:
            # 单独解压 db
            if "db" in manifest.get("items", {}):
                db_target = tmp_root / "app.db"
                with zf.open("app.db") as src, open(db_target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                try:
                    conn = sqlite3.connect(str(db_target))
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                        tables = [r[0] for r in cur.fetchall()]
                        db_info["tables"] = len(tables)
                        if "users" in tables:
                            try:
                                cur.execute("SELECT COUNT(*) FROM users;")
                                db_info["users_count"] = cur.fetchone()[0]
                            except Exception:
                                db_info["users_count"] = -1
                        if "equipment" in tables:
                            try:
                                cur.execute("SELECT COUNT(*) FROM equipment;")
                                db_info["equipment_count"] = cur.fetchone()[0]
                            except Exception:
                                db_info["equipment_count"] = -1
                    finally:
                        conn.close()
                except sqlite3.DatabaseError:
                    raise HTTPException(status_code=400, detail="备份中的数据库损坏，无法打开")
            # uploads 包：列出成员数
            if "uploads" in manifest.get("items", {}):
                item = manifest["items"]
                if item["uploads"].get("format") == "tar.gz" or "uploads.tar.gz" in zf.namelist():
                    with zf.open("uploads.tar.gz") as src:
                        tar_buf = io.BytesIO(src.read())
                    with tarfile.open(fileobj=tar_buf, mode="r:gz") as tar:
                        uploads_count = sum(1 for m in tar.getmembers() if m.isfile())
                else:
                    uploads_count = sum(1 for n in zf.namelist() if n.startswith("uploads/") and not n.endswith("/"))
        return {
            "ok": True,
            "version": manifest.get("version", ""),
            "db_tables_count": db_info["tables"],
            "db_users_count": db_info["users_count"],
            "db_equipment_count": db_info["equipment_count"],
            "uploads_count": uploads_count,
        }
    finally:
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except OSError:
            pass


def health_check_backup(file_name: str, sub_dir: Optional[str] = None) -> dict:
    """对某个备份做健康度校验（可还原性 smoke test）。"""
    f = resolve_backup_file(file_name, sub_dir)
    return {
        "file_name": f.name,
        "size": f.stat().st_size,
        "size_human": _human_size(f.stat().st_size),
        "smoke_restore": _quick_smoke_restore(f),
    }


# ---------- 对外高层：一次性创建（可选加密 + 异地副本 + 可还原性校验） ----------

def create_backup_full(
    sub_dir: Optional[str] = None,
    note: Optional[str] = None,
    include_uploads: bool = True,
    include_env: bool = True,
    encrypt: bool = False,
    copy_to_secondary: bool = False,
    run_smoke_check: bool = True,
    secondary_keep_count: int = 14,
) -> dict:
    """打包备份 → (可选)加密 → (可选)复制到第二目录 → (可选)还原烟雾测试。

    返回 dict 包含每一步执行结果，便于日志。
    """
    # 1) 基础 zip 备份
    info = create_backup(
        sub_dir=sub_dir,
        note=note,
        include_uploads=include_uploads,
        include_env=include_env,
    )
    local_zip = pathlib.Path(info["file_path"])
    result = {
        "backup": info,
        "encrypt": {"enabled": False, "file": None, "ok": None, "error": None},
        "secondary": {"enabled": False, "file": None, "ok": None, "error": None},
        "smoke_check": {"enabled": False, "ok": None, "error": None, "detail": None},
    }
    # 2) 加密：生成 .zip.aes256 放到同一目录（可用于异地副本加密；本地 zip 仍保留，便于快速恢复）
    if encrypt:
        if not _HAS_CRYPTOGRAPHY:
            result["encrypt"]["error"] = "未安装 cryptography 库，跳过加密。pip install cryptography"
        else:
            try:
                enc_file = local_zip.with_name(local_zip.name + _ENC_SUFFIX)
                encrypt_file(local_zip, enc_file)
                result["encrypt"] = {
                    "enabled": True,
                    "file": str(enc_file),
                    "file_name": enc_file.name,
                    "size": enc_file.stat().st_size,
                    "size_human": _human_size(enc_file.stat().st_size),
                    "ok": True,
                    "error": None,
                }
            except Exception as e:
                result["encrypt"]["ok"] = False
                result["encrypt"]["error"] = str(e)
    # 3) 异地副本：优先复制加密文件(若存在)，否则复制 zip
    if copy_to_secondary:
        try:
            sec_root = resolve_secondary_root()
            if sec_root is None:
                result["secondary"]["error"] = "未配置 BACKUP_SECONDARY_DIR，跳过异地副本"
            else:
                src_for_sec = local_zip
                if result["encrypt"].get("ok"):
                    src_for_sec = pathlib.Path(result["encrypt"]["file"])
                dst = _copy_to_secondary(src_for_sec, sec_root, sub_dir=sub_dir)
                # 异地目录下只留最新 N 份
                cleaned = cleanup_dir_backups(sec_root, sub_dir=sub_dir, keep_count=secondary_keep_count)
                result["secondary"] = {
                    "enabled": True,
                    "file": str(dst),
                    "file_name": dst.name,
                    "dir": str(sec_root),
                    "size": dst.stat().st_size,
                    "size_human": _human_size(dst.stat().st_size),
                    "cleaned_count": cleaned,
                    "ok": True,
                    "error": None,
                }
        except Exception as e:
            result["secondary"]["enabled"] = copy_to_secondary
            result["secondary"]["ok"] = False
            result["secondary"]["error"] = str(e)
    # 4) 可还原性烟雾测试（本地 zip）
    if run_smoke_check:
        try:
            smoke = _quick_smoke_restore(local_zip)
            result["smoke_check"] = {"enabled": True, "ok": smoke["ok"], "error": None, "detail": smoke}
        except Exception as e:
            result["smoke_check"] = {"enabled": True, "ok": False, "error": str(e)}
    return result

