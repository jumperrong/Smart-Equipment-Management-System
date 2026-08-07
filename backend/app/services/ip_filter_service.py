"""IP 白名单与访问日志服务。

核心职责：
- is_ip_allowed(ip) 判断 IP 是否在白名单
- log_access_attempt(ip, path, method, ua) 记录未授权访问
- add_to_whitelist / remove_from_whitelist
- approve_pending_ip / reject_pending_ip
- list_access_logs / list_whitelist
- is_whitelist_enabled / set_whitelist_enabled
"""
import ipaddress
from datetime import datetime
from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import IPWhitelist, IPAccessLog, User
from app.services.system_setting_service import (
    get_setting_value, set_setting_value,
)


# 永远隐式允许的 IP（避免锁死本机）
ALWAYS_ALLOWED = {"127.0.0.1", "::1", "localhost"}


# ---------- 白名单开关 ----------

WHITELIST_ENABLED_KEY = "IP_WHITELIST_ENABLED"


def is_whitelist_enabled(db: Session) -> bool:
    """白名单是否启用。默认禁用，避免误锁死。"""
    val = get_setting_value(db, WHITELIST_ENABLED_KEY)
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "on")
    return bool(val)


def set_whitelist_enabled(db: Session, enabled: bool) -> None:
    set_setting_value(db, WHITELIST_ENABLED_KEY, enabled)


# ---------- 白名单查询 ----------

def list_whitelist(db: Session, include_inactive: bool = False) -> List[dict]:
    """返回白名单列表。"""
    q = db.query(IPWhitelist)
    if not include_inactive:
        q = q.filter(IPWhitelist.is_active.is_(True))
    rows = q.order_by(IPWhitelist.id.asc()).all()
    return [_whitelist_to_dict(r) for r in rows]


def _whitelist_to_dict(r: IPWhitelist) -> dict:
    return {
        "id": r.id,
        "ip": r.ip,
        "label": r.label,
        "is_active": r.is_active,
        "created_by": r.created_by,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


# ---------- IP 检查 ----------

def _load_whitelist_networks(db: Session) -> List[tuple[str, ipaddress._BaseNetwork]]:
    """从 DB 加载白名单，返回 (ip/network 对象) 列表。"""
    rows = db.query(IPWhitelist).filter(IPWhitelist.is_active.is_(True)).all()
    result = []
    for r in rows:
        try:
            if "/" in r.ip:
                # CIDR
                net = ipaddress.ip_network(r.ip, strict=False)
                result.append((r.ip, net))
            else:
                # 单个 IP
                addr = ipaddress.ip_address(r.ip)
                result.append((r.ip, ipaddress.ip_network(f"{addr}/32" if addr.version == 4 else f"{addr}/128")))
        except (ValueError, TypeError):
            continue
    return result


def is_ip_allowed(db: Session, ip: str) -> bool:
    """判断 IP 是否允许访问。

    - 白名单未启用：允许所有
    - 白名单启用：本机 IP 永远允许；其余在白名单或 CIDR 内允许
    """
    if not is_whitelist_enabled(db):
        return True

    if not ip:
        return True  # 未知 IP 视为本机(反向代理未配置时)

    # 本机永远允许
    if ip in ALWAYS_ALLOWED:
        return True

    networks = _load_whitelist_networks(db)
    if not networks:
        # 启用了白名单但白名单为空 → 拒绝所有非本机
        return False

    try:
        addr = ipaddress.ip_address(ip)
    except (ValueError, TypeError):
        return False

    for _, net in networks:
        if addr in net:
            return True
    return False


# ---------- 访问日志 ----------

def log_access_attempt(
    db: Session,
    ip: str,
    path: Optional[str] = None,
    method: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> IPAccessLog:
    """记录一次未授权访问尝试。

    - 同一 IP 已有 PENDING 记录则增加 attempt_count 并更新 last_attempt_at
    - 否则新建记录
    """
    ua_short = (user_agent or "")[:500] if user_agent else None

    existing = (
        db.query(IPAccessLog)
        .filter(IPAccessLog.ip == ip, IPAccessLog.status == "PENDING")
        .first()
    )
    if existing:
        existing.attempt_count += 1
        existing.last_attempt_at = datetime.utcnow()
        existing.path = path or existing.path
        existing.method = method or existing.method
        existing.user_agent = ua_short or existing.user_agent
    else:
        existing = IPAccessLog(
            ip=ip,
            path=path,
            method=method,
            user_agent=ua_short,
            status="PENDING",
            attempt_count=1,
            first_attempt_at=datetime.utcnow(),
            last_attempt_at=datetime.utcnow(),
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def list_access_logs(
    db: Session,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[dict]:
    """返回访问日志列表。status 可选 PENDING/APPROVED/REJECTED/None(全部)。"""
    q = db.query(IPAccessLog)
    if status:
        q = q.filter(IPAccessLog.status == status)
    rows = q.order_by(desc(IPAccessLog.last_attempt_at)).limit(limit).all()
    return [_access_log_to_dict(r) for r in rows]


def _access_log_to_dict(r: IPAccessLog) -> dict:
    return {
        "id": r.id,
        "ip": r.ip,
        "path": r.path,
        "method": r.method,
        "user_agent": r.user_agent,
        "status": r.status,
        "attempt_count": r.attempt_count,
        "first_attempt_at": r.first_attempt_at.isoformat() if r.first_attempt_at else None,
        "last_attempt_at": r.last_attempt_at.isoformat() if r.last_attempt_at else None,
        "approved_by": r.approved_by,
        "approved_at": r.approved_at.isoformat() if r.approved_at else None,
        "remark": r.remark,
    }


# ---------- 白名单 CRUD ----------

def add_to_whitelist(
    db: Session,
    ip: str,
    label: Optional[str] = None,
    user: Optional[User] = None,
) -> dict:
    """把 IP 加入白名单。已存在则启用。"""
    ip = (ip or "").strip()
    if not ip:
        raise HTTPException(status_code=400, detail="IP 不能为空")

    # 校验 IP/CIDR
    try:
        if "/" in ip:
            ipaddress.ip_network(ip, strict=False)
        else:
            ipaddress.ip_address(ip)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"IP/CIDR 格式错误: {ip}")

    existing = db.query(IPWhitelist).filter(IPWhitelist.ip == ip).first()
    if existing:
        existing.is_active = True
        if label is not None:
            existing.label = label
        existing.updated_at = datetime.utcnow()
        if user is not None:
            existing.created_by = user.id
        db.commit()
        db.refresh(existing)
        return _whitelist_to_dict(existing)

    row = IPWhitelist(
        ip=ip,
        label=label,
        is_active=True,
        created_by=user.id if user else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _whitelist_to_dict(row)


def remove_from_whitelist(db: Session, whitelist_id: int) -> bool:
    """从白名单删除（包括所有记录）。"""
    row = db.query(IPWhitelist).filter(IPWhitelist.id == whitelist_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def toggle_whitelist_entry(db: Session, whitelist_id: int, is_active: bool) -> dict:
    """启用/停用白名单条目。"""
    row = db.query(IPWhitelist).filter(IPWhitelist.id == whitelist_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="白名单条目不存在")
    row.is_active = is_active
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _whitelist_to_dict(row)


# ---------- 待审 IP 批准/拒绝 ----------

def approve_pending_ip(
    db: Session,
    log_id: int,
    label: Optional[str] = None,
    user: Optional[User] = None,
) -> dict:
    """把待审 IP 加入白名单。

    - 同时更新 IPAccessLog 状态为 APPROVED
    - 调用 add_to_whitelist 加入 IPWhitelist
    """
    log = db.query(IPAccessLog).filter(IPAccessLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="访问日志不存在")
    if log.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"该日志已处理，状态: {log.status}")

    # 加入白名单
    add_to_whitelist(db, log.ip, label=label or f"待审批准-{log.ip}", user=user)

    # 更新日志状态
    log.status = "APPROVED"
    log.approved_by = user.id if user else None
    log.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(log)
    return _access_log_to_dict(log)


def reject_pending_ip(db: Session, log_id: int, user: Optional[User] = None) -> dict:
    """拒绝待审 IP（仅标记状态，不加入白名单）。"""
    log = db.query(IPAccessLog).filter(IPAccessLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="访问日志不存在")
    if log.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"该日志已处理，状态: {log.status}")
    log.status = "REJECTED"
    log.approved_by = user.id if user else None
    log.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(log)
    return _access_log_to_dict(log)


def approve_all_pending(db: Session, user: Optional[User] = None) -> dict:
    """把所有 PENDING 日志对应的 IP 一键加入白名单。"""
    pending = db.query(IPAccessLog).filter(IPAccessLog.status == "PENDING").all()
    approved_count = 0
    skipped = []
    for log in pending:
        try:
            add_to_whitelist(db, log.ip, label=f"待审批准-{log.ip}", user=user)
            log.status = "APPROVED"
            log.approved_by = user.id if user else None
            log.approved_at = datetime.utcnow()
            approved_count += 1
        except HTTPException:
            skipped.append({"id": log.id, "ip": log.ip, "reason": "格式错误"})
    db.commit()
    return {"approved": approved_count, "skipped": skipped}


# ---------- 统计 ----------

def get_whitelist_stats(db: Session) -> dict:
    """返回 IP 白名单相关统计。"""
    whitelist_count = db.query(IPWhitelist).filter(IPWhitelist.is_active.is_(True)).count()
    pending_count = db.query(IPAccessLog).filter(IPAccessLog.status == "PENDING").count()
    return {
        "whitelist_enabled": is_whitelist_enabled(db),
        "whitelist_count": whitelist_count,
        "pending_count": pending_count,
        "always_allowed": list(ALWAYS_ALLOWED),
    }
