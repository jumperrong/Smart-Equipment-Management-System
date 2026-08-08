from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.models import UserRole
from app.services import permission_service
from app.services import system_setting_service
from app.services import ip_filter_service
from app.services import restart_service
from app.services import backup_service
from app.services import backup_scheduler
from app.services.user_service import get_current_user, require_roles

router = APIRouter(prefix="/system", tags=["系统配置"])


# ---------- Schemas（内联，避免改动 schemas/__init__.py） ----------

class PermissionFeature(BaseModel):
    key: str
    label: str
    group: str


class PermissionMatrixOut(BaseModel):
    features: List[PermissionFeature]
    roles: List[str]
    matrix: dict  # {feature_key: {role_value: bool}}


class PermissionUpdateItem(BaseModel):
    role: str
    feature_key: str
    allowed: bool


class PermissionUpdatePayload(BaseModel):
    updates: List[PermissionUpdateItem]


class MyPermissionsOut(BaseModel):
    role: str
    permissions: dict  # {feature_key: bool}


# ---------- 权限矩阵管理（硬编码 admin，避免权限矩阵被改坏后锁死） ----------

@router.get(
    "/permissions",
    response_model=PermissionMatrixOut,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def get_permissions(db: Session = Depends(get_db)):
    """返回角色×功能权限矩阵，供前端配置界面渲染。"""
    return permission_service.get_permission_matrix(db)


@router.put(
    "/permissions",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def update_permissions(
    payload: PermissionUpdatePayload,
    db: Session = Depends(get_db),
):
    """批量更新角色-功能权限。payload.updates 为 [{role, feature_key, allowed}]。"""
    if not payload.updates:
        return {"ok": True, "affected": 0}
    affected = permission_service.update_permissions(db, [u.model_dump() for u in payload.updates])
    return {"ok": True, "affected": affected}


# ---------- 当前用户权限（任意登录用户可查自己） ----------

@router.get("/my-permissions", response_model=MyPermissionsOut)
def get_my_permissions(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回当前用户角色对应的所有 feature_key 放行情况。

    供前端 user store 在 fetchMe 后调用，决定按钮/菜单可见性。
    """
    perms = permission_service.get_my_permissions(db, current_user.role)
    return {"role": current_user.role.value, "permissions": perms}


# ---------- 系统设置（环境变量可视化编辑） ----------

class SettingsUpdateItem(BaseModel):
    key: str
    value: Optional[object] = None  # 任意类型：string/int/float/bool/list/dict


class SettingsUpdatePayload(BaseModel):
    updates: List[SettingsUpdateItem]


@router.get(
    "/settings",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def get_system_settings(db: Session = Depends(get_db)):
    """返回所有可配置环境变量项（含当前生效值、DB设置值、是否需重启）。"""
    return {"items": system_setting_service.get_all_settings(db)}


@router.put(
    "/settings",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def update_system_settings(
    payload: SettingsUpdatePayload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """批量更新系统设置项。

    - 跳过 readonly 项
    - 同步写入 .env 文件
    - 大部分项需重启服务后生效
    """
    updates_dict = {item.key: item.value for item in payload.updates}
    result = system_setting_service.update_settings(db, updates_dict, user=current_user)
    return result


@router.post(
    "/settings/regenerate-secret-key",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def regenerate_secret_key(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """重新生成 JWT 签名密钥。

    生成后所有现有 token 失效，重启服务后需重新登录。
    """
    return system_setting_service.regenerate_secret_key(db, user=current_user)


# ---------- 重启服务 ----------

@router.post(
    "/settings/restart-server",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def restart_server(
    current_user=Depends(get_current_user),
):
    """重启后端服务。

    - 启动一个 detached 子进程，当前进程退出
    - 客户端应等待 5-10 秒后重新连接
    """
    return restart_service.restart_server()


# ---------- IP 白名单 ----------

class WhitelistAddIn(BaseModel):
    ip: str
    label: Optional[str] = None


class WhitelistToggleIn(BaseModel):
    is_active: bool


class WhitelistEnabledIn(BaseModel):
    enabled: bool


@router.get(
    "/ip-whitelist",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def get_ip_whitelist(
    db: Session = Depends(get_db),
    include_inactive: bool = False,
):
    """返回 IP 白名单列表。"""
    return {
        "items": ip_filter_service.list_whitelist(db, include_inactive=include_inactive),
        "stats": ip_filter_service.get_whitelist_stats(db),
    }


@router.post(
    "/ip-whitelist",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def add_ip_to_whitelist(
    payload: WhitelistAddIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """添加 IP 到白名单。"""
    return ip_filter_service.add_to_whitelist(db, payload.ip, payload.label, user=current_user)


@router.delete(
    "/ip-whitelist/{whitelist_id}",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def remove_ip_from_whitelist(
    whitelist_id: int,
    db: Session = Depends(get_db),
):
    """从白名单删除 IP。"""
    ok = ip_filter_service.remove_from_whitelist(db, whitelist_id)
    return {"ok": ok}


@router.put(
    "/ip-whitelist/{whitelist_id}",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def toggle_ip_whitelist(
    whitelist_id: int,
    payload: WhitelistToggleIn,
    db: Session = Depends(get_db),
):
    """启用/停用白名单条目。"""
    return ip_filter_service.toggle_whitelist_entry(db, whitelist_id, payload.is_active)


@router.put(
    "/ip-whitelist-enabled",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def set_whitelist_enabled(
    payload: WhitelistEnabledIn,
    db: Session = Depends(get_db),
):
    """启用/禁用 IP 白名单功能（总开关）。"""
    ip_filter_service.set_whitelist_enabled(db, payload.enabled)
    return {
        "ok": True,
        "enabled": payload.enabled,
        "stats": ip_filter_service.get_whitelist_stats(db),
    }


# ---------- IP 访问日志（待审 IP） ----------

@router.get(
    "/ip-access-logs",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def get_ip_access_logs(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    limit: int = 100,
):
    """返回 IP 访问日志列表。status 可选 PENDING/APPROVED/REJECTED/None(全部)。"""
    return {
        "items": ip_filter_service.list_access_logs(db, status=status, limit=limit),
        "stats": ip_filter_service.get_whitelist_stats(db),
    }


class ApproveIn(BaseModel):
    label: Optional[str] = None


@router.post(
    "/ip-access-logs/{log_id}/approve",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def approve_pending_ip(
    log_id: int,
    payload: ApproveIn = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """批准待审 IP，加入白名单。"""
    label = payload.label if payload else None
    return ip_filter_service.approve_pending_ip(db, log_id, label=label, user=current_user)


@router.post(
    "/ip-access-logs/{log_id}/reject",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def reject_pending_ip(
    log_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """拒绝待审 IP（不加入白名单）。"""
    return ip_filter_service.reject_pending_ip(db, log_id, user=current_user)


@router.post(
    "/ip-access-logs/approve-all",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def approve_all_pending_ips(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """一键批准所有待审 IP 加入白名单。"""
    return ip_filter_service.approve_all_pending(db, user=current_user)


# ---------- Schemas：备份恢复 ----------

class BackupCreateIn(BaseModel):
    sub_dir: Optional[str] = Field("", description="备份子目录名（相对 backups/，留空使用默认根目录）")
    note: Optional[str] = Field("", description="备注")
    include_uploads: bool = True
    include_env: bool = True


class BackupRestoreIn(BaseModel):
    file_name: str
    sub_dir: Optional[str] = ""
    restore_db: bool = True
    restore_uploads: bool = True
    restore_env: bool = True
    skip_auto_snapshot: bool = Field(False, description="跳过自动快照（仅高级用户）")


class BackupDeleteIn(BaseModel):
    file_name: str
    sub_dir: Optional[str] = ""


# ---------- 备份/恢复 API ----------

@router.get(
    "/backup/stats",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def backup_stats(
    sub_dir: Optional[str] = Query("", description="备份子目录"),
):
    """备份统计（数量、大小、最近备份时间）。"""
    return backup_service.backup_stats(sub_dir or None)


@router.get(
    "/backup/list",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def list_backups(
    sub_dir: Optional[str] = Query("", description="备份子目录"),
):
    """列出备份列表（倒序）。"""
    return {"items": backup_service.list_backups(sub_dir or None)}


@router.post(
    "/backup/create",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def create_backup(payload: BackupCreateIn):
    """创建系统完整备份（基础zip版）。"""
    return backup_service.create_backup(
        sub_dir=payload.sub_dir or None,
        note=payload.note or None,
        include_uploads=payload.include_uploads,
        include_env=payload.include_env,
    )


class BackupCreateFullIn(BaseModel):
    sub_dir: Optional[str] = ""
    note: Optional[str] = ""
    include_uploads: bool = True
    include_env: bool = True
    encrypt: bool = False
    copy_to_secondary: bool = False
    run_smoke_check: bool = True
    secondary_keep_count: int = Field(14, ge=1, description="异地目录保留份数")


@router.post(
    "/backup/create-full",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def create_backup_full(payload: BackupCreateFullIn):
    """一键备份：zip → 加密 → 异地副本 → 还原烟雾测试。"""
    return backup_service.create_backup_full(
        sub_dir=payload.sub_dir or None,
        note=payload.note or None,
        include_uploads=payload.include_uploads,
        include_env=payload.include_env,
        encrypt=payload.encrypt,
        copy_to_secondary=payload.copy_to_secondary,
        run_smoke_check=payload.run_smoke_check,
        secondary_keep_count=payload.secondary_keep_count,
    )


@router.get(
    "/backup/security-status",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def backup_security_status():
    """查看备份加密 / 异地副本是否配置。"""
    enc_status = backup_service.is_backup_encryption_available()
    try:
        sec_dir = backup_service.resolve_secondary_root()
        secondary = {"configured": True, "dir": str(sec_dir)}
    except Exception as e:
        secondary = {"configured": False, "error": str(e)}
    return {"encryption": enc_status, "secondary": secondary}


@router.post(
    "/backup/health-check",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def backup_health_check(payload: BackupDeleteIn):
    """对某备份文件做可还原性烟雾测试。"""
    return backup_service.health_check_backup(payload.file_name, payload.sub_dir or None)


@router.delete(
    "/backup/delete",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def delete_backup(payload: BackupDeleteIn):
    """删除单个备份文件。"""
    ok = backup_service.delete_backup(payload.file_name, payload.sub_dir or None)
    return {"ok": ok}


@router.post(
    "/backup/restore",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def restore_backup(
    payload: BackupRestoreIn,
    current_user=Depends(get_current_user),
):
    """从备份恢复系统全部数据。

    - 默认先做自动快照
    - 恢复后需重启服务
    """
    return backup_service.restore_backup(
        file_name=payload.file_name,
        sub_dir=payload.sub_dir or None,
        restore_db=payload.restore_db,
        restore_uploads=payload.restore_uploads,
        restore_env=payload.restore_env,
        skip_auto_snapshot=payload.skip_auto_snapshot,
    )


@router.get(
    "/backup/download",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def download_backup(
    file_name: str,
    sub_dir: Optional[str] = Query("", description="备份子目录"),
):
    """下载单个备份 .zip 文件。"""
    p = backup_service.resolve_backup_file(file_name, sub_dir or None)
    return FileResponse(
        path=str(p),
        filename=file_name,
        media_type="application/zip",
    )


# ---------- Schemas：定时备份 ----------

class BackupScheduleIn(BaseModel):
    enabled: bool = Field(False, description="是否启用定时备份")
    cron: str = Field("0 2 * * *", description="cron 表达式（5字段：分 时 日 月 周）")
    sub_dir: str = Field("scheduled", description="备份子目录")
    keep_count: int = Field(30, ge=0, description="本地保留备份数量（0=不限制）")
    secondary_keep_count: int = Field(14, ge=1, description="异地目录保留份数")
    include_uploads: bool = True
    include_env: bool = True
    encrypt: bool = Field(False, description="备份后生成 .aes256 加密副本（需安装 cryptography）")
    copy_to_secondary: bool = Field(False, description="把备份复制到 BACKUP_SECONDARY_DIR 第二目录")
    run_smoke_check: bool = Field(True, description="备份后做一次还原烟雾测试（验证可恢复性）")


# ---------- 定时备份 API ----------

@router.get(
    "/backup/schedule",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def get_backup_schedule():
    """获取定时备份配置和运行状态。"""
    return backup_scheduler.get_schedule_status()


@router.put(
    "/backup/schedule",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def update_backup_schedule(payload: BackupScheduleIn):
    """更新定时备份配置（立即生效，无需重启）。"""
    return backup_scheduler.update_schedule_config(
        enabled=payload.enabled,
        cron=payload.cron,
        sub_dir=payload.sub_dir,
        keep_count=payload.keep_count,
        include_uploads=payload.include_uploads,
        include_env=payload.include_env,
        secondary_keep_count=payload.secondary_keep_count,
        encrypt=payload.encrypt,
        copy_to_secondary=payload.copy_to_secondary,
        run_smoke_check=payload.run_smoke_check,
    )


@router.post(
    "/backup/schedule/trigger",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def trigger_backup_now():
    """立即触发一次定时备份。"""
    return backup_scheduler.trigger_now()
