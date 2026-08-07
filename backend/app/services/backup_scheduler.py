"""定时备份调度器。

使用 APScheduler BackgroundScheduler 在后台线程中定时执行备份。
配置存储在 system_settings 表中（不写 .env，无需重启即可生效）。

配置项（均通过 system_setting_service.get/set_setting_value 读写）：
- BACKUP_SCHEDULE_ENABLED (bool): 是否启用定时备份
- BACKUP_SCHEDULE_CRON (str): cron 表达式（5字段：分 时 日 月 周，如 "0 2 * * *" = 每天2点）
- BACKUP_SCHEDULE_SUB_DIR (str): 备份子目录（如 "scheduled"）
- BACKUP_SCHEDULE_KEEP_COUNT (int): 保留备份数量（0=不限制）
- BACKUP_SCHEDULE_INCLUDE_UPLOADS (bool): 是否包含上传文件
- BACKUP_SCHEDULE_INCLUDE_ENV (bool): 是否包含 .env
- BACKUP_SCHEDULE_LAST_RUN (str): 上次执行时间（ISO）
- BACKUP_SCHEDULE_LAST_STATUS (str): 上次执行状态摘要
"""
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.database import SessionLocal
from app.services import backup_service
from app.services import system_setting_service

logger = logging.getLogger(__name__)

JOB_ID = "scheduled_backup"

# 默认配置
DEFAULTS = {
    "BACKUP_SCHEDULE_ENABLED": False,
    "BACKUP_SCHEDULE_CRON": "0 2 * * *",
    "BACKUP_SCHEDULE_SUB_DIR": "scheduled",
    "BACKUP_SCHEDULE_KEEP_COUNT": 30,
    "BACKUP_SCHEDULE_INCLUDE_UPLOADS": True,
    "BACKUP_SCHEDULE_INCLUDE_ENV": True,
}

_scheduler: Optional[BackgroundScheduler] = None


# ---------- 配置读写 ----------

def _get_config() -> dict:
    db = SessionLocal()
    try:
        return {
            "enabled": system_setting_service.get_setting_value(
                db, "BACKUP_SCHEDULE_ENABLED", DEFAULTS["BACKUP_SCHEDULE_ENABLED"]
            ),
            "cron": system_setting_service.get_setting_value(
                db, "BACKUP_SCHEDULE_CRON", DEFAULTS["BACKUP_SCHEDULE_CRON"]
            ),
            "sub_dir": system_setting_service.get_setting_value(
                db, "BACKUP_SCHEDULE_SUB_DIR", DEFAULTS["BACKUP_SCHEDULE_SUB_DIR"]
            ),
            "keep_count": system_setting_service.get_setting_value(
                db, "BACKUP_SCHEDULE_KEEP_COUNT", DEFAULTS["BACKUP_SCHEDULE_KEEP_COUNT"]
            ),
            "include_uploads": system_setting_service.get_setting_value(
                db, "BACKUP_SCHEDULE_INCLUDE_UPLOADS", DEFAULTS["BACKUP_SCHEDULE_INCLUDE_UPLOADS"]
            ),
            "include_env": system_setting_service.get_setting_value(
                db, "BACKUP_SCHEDULE_INCLUDE_ENV", DEFAULTS["BACKUP_SCHEDULE_INCLUDE_ENV"]
            ),
            "last_run": system_setting_service.get_setting_value(
                db, "BACKUP_SCHEDULE_LAST_RUN", None
            ),
            "last_status": system_setting_service.get_setting_value(
                db, "BACKUP_SCHEDULE_LAST_STATUS", None
            ),
        }
    finally:
        db.close()


def _set_last_run(status: str):
    db = SessionLocal()
    try:
        now = datetime.now().isoformat(timespec="seconds")
        system_setting_service.set_setting_value(db, "BACKUP_SCHEDULE_LAST_RUN", now)
        system_setting_service.set_setting_value(db, "BACKUP_SCHEDULE_LAST_STATUS", status)
    finally:
        db.close()


# ---------- 定时任务执行体 ----------

def _run_backup():
    """定时任务执行体：创建备份 + 清理旧备份。"""
    config = _get_config()
    now_str = datetime.now().isoformat(timespec="seconds")

    try:
        info = backup_service.create_backup(
            sub_dir=config["sub_dir"] or None,
            note=f"定时备份 ({now_str})",
            include_uploads=config["include_uploads"],
            include_env=config["include_env"],
        )
        # 清理旧备份
        cleaned = 0
        if config["keep_count"] and config["keep_count"] > 0:
            cleaned = _cleanup_old_backups(config["sub_dir"], config["keep_count"])

        status = f"成功: {info['file_name']} ({info['size_human']})"
        if cleaned:
            status += f"，已清理 {cleaned} 个旧备份"
        logger.info("定时备份%s", status)
        _set_last_run(status)
    except Exception as e:
        logger.error("定时备份失败: %s", e, exc_info=True)
        _set_last_run(f"失败: {e}")


def _cleanup_old_backups(sub_dir: str, keep_count: int) -> int:
    """保留最近 keep_count 个备份，删除更旧的。返回已删除数量。"""
    backups = backup_service.list_backups(sub_dir)
    if len(backups) <= keep_count:
        return 0
    deleted = 0
    for old in backups[keep_count:]:
        try:
            backup_service.delete_backup(old["file_name"], sub_dir)
            deleted += 1
            logger.info("已清理过期定时备份: %s", old["file_name"])
        except Exception as e:
            logger.warning("清理备份失败 %s: %s", old["file_name"], e)
    return deleted


# ---------- 调度器生命周期 ----------

def start_scheduler():
    """启动调度器（在应用 lifespan 中调用）。"""
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.start()
    logger.info("定时备份调度器已启动")
    reload_scheduler()


def stop_scheduler():
    """停止调度器（在应用 lifespan 中调用）。"""
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("定时备份调度器已停止")


def reload_scheduler():
    """重新加载配置并更新调度任务。

    在配置变更后调用，使新配置立即生效（无需重启服务）。
    """
    global _scheduler
    if _scheduler is None:
        return

    # 先移除旧任务
    try:
        _scheduler.remove_job(JOB_ID)
    except Exception:
        pass

    config = _get_config()
    if not config["enabled"]:
        logger.info("定时备份未启用")
        return

    try:
        trigger = CronTrigger.from_crontab(config["cron"])
    except Exception as e:
        logger.error("cron 表达式无效: %s (%s)", config["cron"], e)
        return

    _scheduler.add_job(
        _run_backup,
        trigger=trigger,
        id=JOB_ID,
        name="定时备份",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )
    job = _scheduler.get_job(JOB_ID)
    logger.info(
        "定时备份已调度: cron='%s', 下次执行: %s",
        config["cron"],
        job.next_run_time if job else "未知",
    )


# ---------- 状态查询 & 配置更新 ----------

def get_schedule_status() -> dict:
    """返回调度器状态和配置。"""
    config = _get_config()
    next_run = None
    if _scheduler is not None:
        job = _scheduler.get_job(JOB_ID)
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat(timespec="seconds")
    return {
        **config,
        "running": _scheduler is not None and _scheduler.running,
        "next_run": next_run,
    }


def update_schedule_config(
    enabled: bool,
    cron: str,
    sub_dir: str,
    keep_count: int,
    include_uploads: bool,
    include_env: bool,
) -> dict:
    """更新定时备份配置并重新调度。"""
    # 校验 cron 表达式
    try:
        CronTrigger.from_crontab(cron)
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"cron 表达式无效: {e}")

    db = SessionLocal()
    try:
        system_setting_service.set_setting_value(db, "BACKUP_SCHEDULE_ENABLED", enabled)
        system_setting_service.set_setting_value(db, "BACKUP_SCHEDULE_CRON", cron)
        system_setting_service.set_setting_value(db, "BACKUP_SCHEDULE_SUB_DIR", sub_dir)
        system_setting_service.set_setting_value(db, "BACKUP_SCHEDULE_KEEP_COUNT", keep_count)
        system_setting_service.set_setting_value(db, "BACKUP_SCHEDULE_INCLUDE_UPLOADS", include_uploads)
        system_setting_service.set_setting_value(db, "BACKUP_SCHEDULE_INCLUDE_ENV", include_env)
    finally:
        db.close()

    reload_scheduler()
    return get_schedule_status()


def trigger_now() -> dict:
    """立即执行一次定时备份（同步，等待完成后返回结果）。"""
    config = _get_config()
    now_str = datetime.now().isoformat(timespec="seconds")

    try:
        info = backup_service.create_backup(
            sub_dir=config["sub_dir"] or None,
            note=f"手动触发定时备份 ({now_str})",
            include_uploads=config["include_uploads"],
            include_env=config["include_env"],
        )
        cleaned = 0
        if config["keep_count"] and config["keep_count"] > 0:
            cleaned = _cleanup_old_backups(config["sub_dir"], config["keep_count"])
        status = f"成功: {info['file_name']} ({info['size_human']})"
        if cleaned:
            status += f"，已清理 {cleaned} 个旧备份"
        _set_last_run(status)
    except Exception as e:
        _set_last_run(f"失败: {e}")
        raise

    return {
        "ok": True,
        "backup": info,
        "cleaned": cleaned,
        "status": status,
    }
