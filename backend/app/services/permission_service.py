"""角色-功能权限服务。

核心 API：
- is_allowed(db, role, feature_key) → bool
    查 DB role_permissions 表；无记录则回退到 constants.default_allowed 默认值
- require_permission(feature_key) → FastAPI 依赖
    与现有 require_roles 等价的装饰器，但走 DB 驱动
- seed_default_permissions(db)
    启动时把缺失的 (role, feature_key) 按默认值补齐到 DB
- get_permission_matrix(db) → dict
    返回完整角色×功能矩阵供前端渲染
- update_permissions(db, updates)
    批量更新 allowed 值
- get_my_permissions(db, role) → dict[str, bool]
    返回当前角色所有 feature_key 的放行情况
"""
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.constants import FEATURES, FEATURE_BY_KEY, all_feature_keys, default_allowed
from app.models import RolePermission, UserRole
from app.services.user_service import get_current_user


# ---------- 内部查询 ----------

def _query(db: Session, role: UserRole, feature_key: str) -> Optional[RolePermission]:
    return (
        db.query(RolePermission)
        .filter(RolePermission.role == role, RolePermission.feature_key == feature_key)
        .first()
    )


def is_allowed(db: Session, role: UserRole, feature_key: str) -> bool:
    """角色对该 feature_key 是否放行：DB 有记录取 DB，否则取默认值。"""
    rp = _query(db, role, feature_key)
    if rp is not None:
        return rp.allowed
    return default_allowed(role, feature_key)


# ---------- 权限装饰器 ----------

def require_permission(feature_key: str):
    """FastAPI 依赖：要求当前用户对 feature_key 有权限。

    与 require_roles(*roles) 等价，但走 DB 驱动；管理员可在前端动态调整。
    """
    if feature_key not in FEATURE_BY_KEY:
        # 防御：未知 feature_key 一律拒绝，避免漏配
        def _check_unknown(user=Depends(get_current_user)):
            raise HTTPException(status_code=403, detail=f"权限不足：未知功能 {feature_key}")
        return _check_unknown

    def _check(user=Depends(get_current_user), db=Depends(get_db)):
        if not is_allowed(db, user.role, feature_key):
            raise HTTPException(status_code=403, detail="权限不足")
        return user
    return _check


# ---------- Seed / 初始化 ----------

def seed_default_permissions(db: Session) -> None:
    """启动时补齐缺失的 (role, feature_key) 记录。

    - 不覆盖已有记录（保留管理员调整）
    - 新增 feature 后下次启动自动补齐各角色默认值
    - 同时清理"已废弃"的 feature_key 记录（如果改过清单）
    """
    valid_keys = set(all_feature_keys())
    all_roles = list(UserRole)

    # 1) 补齐缺失
    for role in all_roles:
        for feat in FEATURES:
            existing = _query(db, role, feat.key)
            if existing is None:
                db.add(RolePermission(
                    role=role,
                    feature_key=feat.key,
                    allowed=default_allowed(role, feat.key),
                ))
    db.flush()

    # 2) 清理已废弃（feature_key 不在清单内的记录）
    if valid_keys:
        db.query(RolePermission).filter(
            ~RolePermission.feature_key.in_(valid_keys)
        ).delete(synchronize_session=False)

    db.commit()


# ---------- 矩阵读写 ----------

def get_permission_matrix(db: Session) -> dict:
    """返回完整角色×功能矩阵，供前端配置界面渲染。

    结构：
    {
      "features": [
        {"key": "...", "label": "...", "group": "..."}
      ],
      "roles": ["admin", "engineer", "operator", "viewer"],
      "matrix": {
        "<feature_key>": {
          "admin": true, "engineer": true, ...
        }
      }
    }
    """
    all_rows = db.query(RolePermission).all()
    # (role.value, feature_key) -> allowed
    lookup = {(r.role.value, r.feature_key): r.allowed for r in all_rows}

    matrix = {}
    for feat in FEATURES:
        row = {}
        for role in UserRole:
            key = (role.value, feat.key)
            if key in lookup:
                row[role.value] = lookup[key]
            else:
                # DB 缺失理论上不会发生（seed 已补齐），兜底取默认
                row[role.value] = default_allowed(role, feat.key)
        matrix[feat.key] = row

    return {
        "features": [
            {"key": f.key, "label": f.label, "group": f.group}
            for f in FEATURES
        ],
        "roles": [r.value for r in UserRole],
        "matrix": matrix,
    }


def update_permissions(db: Session, updates: list[dict]) -> int:
    """批量更新 allowed。updates: [{role, feature_key, allowed}]。

    - 不存在的 (role, feature_key) 自动按默认值创建后再更新
    - 返回更新的记录条数
    """
    affected = 0
    for item in updates:
        role_val = item.get("role")
        fkey = item.get("feature_key")
        allowed = bool(item.get("allowed"))
        # 校验 role
        try:
            role = UserRole(role_val)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"未知角色: {role_val}")
        # 校验 feature_key
        if fkey not in FEATURE_BY_KEY:
            raise HTTPException(status_code=400, detail=f"未知功能键: {fkey}")

        rp = _query(db, role, fkey)
        if rp is None:
            rp = RolePermission(role=role, feature_key=fkey, allowed=allowed)
            db.add(rp)
        else:
            rp.allowed = allowed
            rp.updated_at = datetime.utcnow()
        affected += 1
    db.commit()
    return affected


def get_my_permissions(db: Session, role: UserRole) -> dict[str, bool]:
    """返回某角色的所有 feature_key → allowed 映射，供前端 user store 使用。"""
    result = {}
    for feat in FEATURES:
        result[feat.key] = is_allowed(db, role, feat.key)
    return result
