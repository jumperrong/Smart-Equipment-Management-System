"""系统设置服务。

核心职责：
- 把可配置项的"管理员设置值"持久化到 system_settings 表
- 同步写入 .env 文件，重启服务后由 pydantic-settings 自动加载
- 启动时 seed_default_settings 把缺失的 key 用默认值补齐到 DB
- 提供 get_all_settings / update_settings / regenerate_secret_key

设计要点：
- 当前生效值来自 app.core.config.settings（即 .env 文件加载结果）
- DB 中的 value 表示"管理员期望值"，与 settings 比较可判断是否需要重启
- 修改流程：update_settings → 写 DB + 写 .env 文件 → 提示重启
"""
import json
import os
import secrets
import sys
import pathlib
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings as runtime_settings
from app.models import SystemSetting, User
from app.system_setting_defs import SETTING_DEFS, SETTING_BY_KEY, SettingDef


# ---------- 值序列化 ----------

def _serialize_value(value: Any, value_type: str) -> str:
    """把 Python 值序列化为 system_settings.value 列存储的字符串。"""
    if value is None:
        return ""
    if value_type == "json":
        return json.dumps(value, ensure_ascii=False)
    if value_type == "bool":
        return "true" if value else "false"
    return str(value)


def _deserialize_value(raw: Optional[str], value_type: str) -> Any:
    """把存储的字符串还原为 Python 值。"""
    if raw is None or raw == "":
        return None
    if value_type == "int":
        try:
            return int(raw)
        except (ValueError, TypeError):
            return None
    if value_type == "float":
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None
    if value_type == "bool":
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if value_type == "json":
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None
    return raw


def _env_value_for_setting(value: Any, value_type: str) -> str:
    """转换为 .env 文件中 KEY=VALUE 的 VALUE 字符串。"""
    if value is None:
        return ""
    if value_type == "json":
        # JSON 数组在 .env 中用双引号包裹，避免被 pydantic-settings 当成字符串
        return json.dumps(value, ensure_ascii=False)
    if value_type == "bool":
        return "true" if value else "false"
    if value_type in ("int", "float"):
        return str(value)
    # string：含特殊字符用双引号包裹
    s = str(value)
    if any(c in s for c in (" ", "#", "=", '"', "'", "\n")):
        s = s.replace('"', '\\"')
        return f'"{s}"'
    return s


# ---------- 当前生效值 ----------

def _current_effective_value(def_: SettingDef) -> Any:
    """读取运行时 settings 中对应字段的值（来自 .env / 默认值）。"""
    return getattr(runtime_settings, def_.key, def_.default)


# ---------- DB 查询 ----------

def _query(db: Session, key: str) -> Optional[SystemSetting]:
    return db.query(SystemSetting).filter(SystemSetting.key == key).first()


# ---------- Seed ----------

def seed_default_settings(db: Session) -> None:
    """启动时补齐缺失的 system_settings 记录。

    - 不覆盖已有记录（保留管理员设置）
    - 新增的 key 用默认值初始化
    """
    for def_ in SETTING_DEFS:
        existing = _query(db, def_.key)
        if existing is None:
            db.add(SystemSetting(
                key=def_.key,
                value=_serialize_value(def_.default, def_.value_type),
            ))
    db.commit()


# ---------- 单值读写（用于非环境变量类配置项，如 IP_WHITELIST_ENABLED） ----------

def get_setting_value(db: Session, key: str, default: Any = None) -> Any:
    """读取单条 system_setting，类型由 SETTING_BY_KEY 推断；未定义时返回 default。"""
    def_ = SETTING_BY_KEY.get(key)
    if def_ is None:
        # 非环境变量定义项（如 IP_WHITELIST_ENABLED），按 bool 处理
        row = _query(db, key)
        if row is None or row.value is None or row.value == "":
            return default
        # 简单 JSON 解析尝试
        import json as _json
        try:
            return _json.loads(row.value)
        except (ValueError, TypeError):
            s = row.value.strip().lower()
            if s in ("1", "true", "yes", "on"):
                return True
            if s in ("0", "false", "no", "off", ""):
                return False
            return row.value
    row = _query(db, key)
    if row is None:
        return default
    return _deserialize_value(row.value, def_.value_type)


def set_setting_value(db: Session, key: str, value: Any) -> None:
    """写入单条 system_setting（非环境变量类配置项）。

    与 update_settings 不同：不写 .env 文件，仅更新 DB。
    """
    row = _query(db, key)
    if row is None:
        row = SystemSetting(key=key)
        db.add(row)
    # 简单序列化：bool/int/float/json 用 JSON；string 直接
    if isinstance(value, bool):
        row.value = "true" if value else "false"
    elif isinstance(value, (list, dict)):
        import json as _json
        row.value = _json.dumps(value, ensure_ascii=False)
    else:
        row.value = str(value) if value is not None else ""
    row.updated_at = datetime.utcnow()
    db.commit()


# ---------- 读取 ----------

def get_all_settings(db: Session) -> list[dict]:
    """返回所有可配置项的完整信息（含定义、当前生效值、DB设置值、是否需要重启）。"""
    rows = {r.key: r for r in db.query(SystemSetting).all()}

    result = []
    for def_ in SETTING_DEFS:
        row = rows.get(def_.key)
        db_value = _deserialize_value(row.value, def_.value_type) if row else def_.default
        effective = _current_effective_value(def_)

        # 比较 DB 设置值与当前生效值，判断是否需要重启才一致
        needs_restart = def_.requires_restart and (db_value != effective)

        # 敏感值脱敏：仅显示是否已设置 + 长度
        if def_.is_sensitive and not def_.is_readonly:
            display_value = _mask_sensitive(effective)
        elif def_.is_readonly and def_.is_sensitive:
            display_value = _mask_sensitive(effective)
        else:
            display_value = effective

        result.append({
            "key": def_.key,
            "label": def_.label,
            "group": def_.group,
            "value_type": def_.value_type,
            "default": def_.default,
            "description": def_.description,
            "is_sensitive": def_.is_sensitive,
            "is_readonly": def_.is_readonly,
            "requires_restart": def_.requires_restart,
            "sort_order": def_.sort_order,
            # 当前生效值（来自 .env / Settings 默认）
            "effective_value": display_value,
            # DB 中管理员设置的值（用于表单回填）
            "db_value": display_value if def_.is_sensitive else db_value,
            # 是否需要重启才能让 DB 值生效
            "needs_restart": needs_restart,
            "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        })
    return result


def _mask_sensitive(value: Any) -> str:
    """敏感值脱敏为 ****** 格式。"""
    if value is None or value == "":
        return ""
    s = str(value)
    if len(s) <= 8:
        return "*" * len(s)
    return s[:2] + "*" * (len(s) - 6) + s[-4:]


# ---------- 更新 ----------

def update_settings(db: Session, updates: dict, user: Optional[User] = None) -> dict:
    """批量更新配置项。

    updates: {key: value}  value 已是 Python 类型
    - 跳过 readonly 项
    - 跳过未知 key
    - 校验 value 类型
    - 写 DB + 写 .env 文件
    返回 {updated: [...], skipped: [...]}
    """
    updated_keys = []
    skipped = []

    for key, new_value in updates.items():
        def_ = SETTING_BY_KEY.get(key)
        if def_ is None:
            skipped.append({"key": key, "reason": "未知配置项"})
            continue
        if def_.is_readonly:
            skipped.append({"key": key, "reason": "只读项不可修改"})
            continue

        # 类型校验/转换
        try:
            coerced = _coerce_value(new_value, def_.value_type, def_.default)
        except ValueError as e:
            skipped.append({"key": key, "reason": str(e)})
            continue

        row = _query(db, key)
        if row is None:
            row = SystemSetting(key=key)
            db.add(row)
        row.value = _serialize_value(coerced, def_.value_type)
        row.updated_at = datetime.utcnow()
        if user is not None:
            row.updated_by = user.id
        updated_keys.append(key)

    db.commit()

    # 写 .env 文件
    if updated_keys:
        env_written = write_env_file(db)
        return {
            "updated": updated_keys,
            "skipped": skipped,
            "env_file": env_written,
            "requires_restart": True,
        }
    return {"updated": [], "skipped": skipped, "env_file": None, "requires_restart": False}


def _coerce_value(value: Any, value_type: str, default: Any) -> Any:
    """把前端传来的值转换为对应类型。"""
    if value is None or value == "":
        return default
    if value_type == "int":
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ValueError(f"需要整数，得到 {value!r}")
    if value_type == "float":
        try:
            return float(value)
        except (ValueError, TypeError):
            raise ValueError(f"需要数字，得到 {value!r}")
    if value_type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if value_type == "json":
        # 期望是 list 或 dict
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if not isinstance(parsed, (list, dict)):
                    raise ValueError("JSON 必须是数组或对象")
                return parsed
            except (ValueError, TypeError) as e:
                raise ValueError(f"JSON 解析失败: {e}")
        raise ValueError(f"不支持的类型: {type(value)}")
    # string
    return str(value)


# ---------- 写 .env 文件 ----------

def _env_file_path() -> pathlib.Path:
    """返回 .env 文件应写入的路径。

    优先级：
    1. PyInstaller 打包：exe 同级目录（用户数据持久化区）
    2. 开发模式：当前工作目录（一般是 backend/）
    """
    if getattr(sys, "frozen", False):
        # 打包模式：exe 同级目录
        return pathlib.Path(sys.executable).parent / ".env"
    # 开发模式：当前工作目录
    return pathlib.Path.cwd() / ".env"


def write_env_file(db: Session) -> dict:
    """把所有 system_settings 写入 .env 文件。

    策略：
    - 读取现有 .env 内容（若存在），保留未在 SETTING_DEFS 中的行
    - 对 SETTING_DEFS 中的 key 用 DB 值覆盖（DB 缺失则用默认值）
    - 同时更新运行时 settings，使部分非启动参数立即生效（如 token 过期）
    """
    env_path = _env_file_path()
    # 读取现有 .env（保留注释和其他自定义项）
    existing_lines = []
    existing_keys = set()
    if env_path.is_file():
        try:
            with env_path.open("r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        existing_lines.append(line.rstrip("\n"))
                        continue
                    if "=" in stripped:
                        k = stripped.split("=", 1)[0].strip()
                        existing_keys.add(k)
                    existing_lines.append(line.rstrip("\n"))
        except Exception:
            existing_lines = []

    # 计算要写入的 key=value
    rows = {r.key: r for r in db.query(SystemSetting).all()}
    new_lines = []
    written_keys = set()

    # 先保留原有的非可配置项行
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in SETTING_BY_KEY:
                continue  # 跳过，后面重新写
        new_lines.append(line)

    # 追加所有可配置项
    new_lines.append("")
    new_lines.append("# ===== 系统设置（由管理员界面维护，重启后生效） =====")
    for def_ in SETTING_DEFS:
        row = rows.get(def_.key)
        if row and row.value:
            value = _deserialize_value(row.value, def_.value_type)
        else:
            value = def_.default
        env_value = _env_value_for_setting(value, def_.value_type)
        new_lines.append(f"{def_.key}={env_value}")
        written_keys.add(def_.key)
    new_lines.append("# ===== 系统设置结束 =====")
    new_lines.append("")

    try:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        with env_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
    except Exception as e:
        return {"path": str(env_path), "ok": False, "error": str(e)}

    return {"path": str(env_path), "ok": True, "keys": list(written_keys)}


# ---------- SECRET_KEY 重新生成 ----------

def regenerate_secret_key(db: Session, user: Optional[User] = None) -> dict:
    """重新生成 JWT 签名密钥。

    生成 64 字节随机字符串，写入 DB 和 .env 文件。
    重新生成后所有现有 token 失效，需要重新登录。
    """
    def_ = SETTING_BY_KEY.get("SECRET_KEY")
    if def_ is None:
        raise ValueError("SECRET_KEY 配置项未定义")

    new_key = secrets.token_urlsafe(48)  # 约 64 字符
    row = _query(db, "SECRET_KEY")
    if row is None:
        row = SystemSetting(key="SECRET_KEY")
        db.add(row)
    row.value = _serialize_value(new_key, def_.value_type)
    row.updated_at = datetime.utcnow()
    if user is not None:
        row.updated_by = user.id
    db.commit()

    env_info = write_env_file(db)
    return {
        "new_key_masked": _mask_sensitive(new_key),
        "env_file": env_info,
        "requires_restart": True,
        "warning": "重新生成后所有现有登录会失效，重启服务后需重新登录",
    }
