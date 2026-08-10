"""安全审计日志服务。

统一记录登录/改密/用户管理等敏感操作到 audit_logs 表，
替代散落在 auth.py 中的 print("[SEC-AUDIT]...") 调用。
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_audit(
    db: Session,
    action: str,
    actor: Optional[str] = None,
    target: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    """写入一条审计日志。异常时静默降级，不影响主业务流程。"""
    try:
        entry = AuditLog(
            action=action,
            actor=actor,
            target=target,
            ip=ip,
            user_agent=(user_agent or "")[:512] if user_agent else None,
            detail=detail,
        )
        db.add(entry)
        db.commit()
    except Exception:
        # 审计日志写入失败不应阻断登录等核心流程
        try:
            db.rollback()
        except Exception:
            pass
