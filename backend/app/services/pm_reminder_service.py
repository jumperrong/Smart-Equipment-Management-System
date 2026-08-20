"""设备保养 PM 到期提醒服务。

提供 PM 计划到期/逾期查询、汇总统计、手动重算 next_due_date，
以及基于 APScheduler 的每日 8:00 扫描并写入 audit_log 的后台调度器。

依赖：
- PMPlan（pm_plans 表）
- Equipment（equipments 表）
- AuditLog（audit_logs 表）
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

# 调度器时区：显式指定 Asia/Shanghai，避免在 UTC 沙箱中 8:00 实际触发于北京 16:00
_SCHED_TZ = ZoneInfo("Asia/Shanghai")

from app.core.database import SessionLocal
from app.models import AuditLog, Equipment, PMPlan
from app.schemas import PMReminderOut, PMReminderSummary

logger = logging.getLogger(__name__)

JOB_ID = "pm_reminder_scan"

_scheduler: Optional[BackgroundScheduler] = None


# ---------- 查询与提醒 ----------

def list_pm_reminders(
    db: Session,
    days_ahead: int = 7,
    include_overdue: bool = True,
    equipment_id: Optional[int] = None,
    only_active: bool = True,
) -> List[PMReminderOut]:
    """列出未来到期/逾期的 PM 计划提醒。

    - days_ahead: 未来 N 天内到期的计划被纳入
    - include_overdue: 是否包含已逾期计划
    - equipment_id: 仅指定设备
    - only_active: 仅活跃计划（is_active=True）
    排序：is_overdue 优先（True 在前），然后 days_until_due 升序。
    """
    today = datetime.utcnow()
    q = db.query(PMPlan)
    if only_active:
        q = q.filter(PMPlan.is_active.is_(True))
    if equipment_id is not None:
        q = q.filter(PMPlan.equipment_id == equipment_id)

    plans = q.all()

    # 批量取设备名，避免循环内 N+1 查询
    eq_ids = {p.equipment_id for p in plans if p.equipment_id is not None}
    eq_map: dict[int, Equipment] = {}
    if eq_ids:
        for e in db.query(Equipment).filter(Equipment.id.in_(list(eq_ids))).all():
            eq_map[e.id] = e

    items: List[PMReminderOut] = []

    for plan in plans:
        next_due = plan.next_due_date
        if next_due is None:
            days_until_due: Optional[int] = None
            is_overdue = False
        else:
            days_until_due = int((next_due - today).days)
            is_overdue = next_due < today

        # 过滤：逾期（若包含）或未来 N 天内到期
        if is_overdue:
            if not include_overdue:
                continue
        else:
            if days_until_due is None or days_until_due > days_ahead:
                continue

        equipment = eq_map.get(plan.equipment_id)
        equipment_name = equipment.name if equipment else None

        items.append(
            PMReminderOut(
                plan_id=plan.id,
                equipment_id=plan.equipment_id,
                equipment_name=equipment_name,
                plan_name=plan.name,
                cycle_days=plan.cycle_days,
                next_due_date=next_due,
                days_until_due=days_until_due,
                is_overdue=is_overdue,
                is_active=bool(plan.is_active),
                last_executed_at=plan.last_executed_at,
            )
        )

    # 排序：逾期优先，然后 days_until_due 升序（None 放最后）
    items.sort(
        key=lambda x: (
            not x.is_overdue,
            x.days_until_due if x.days_until_due is not None else float("inf"),
        )
    )
    return items


def get_pm_reminder_summary(db: Session, days_ahead: int = 7) -> PMReminderSummary:
    """返回 PM 到期提醒汇总：逾期数、7 天内到期数、30 天内到期数等。"""
    items = list_pm_reminders(
        db, days_ahead=days_ahead, include_overdue=True, only_active=True
    )
    overdue_count = sum(1 for x in items if x.is_overdue)
    due_in_7d_count = sum(
        1 for x in items if not x.is_overdue and x.days_until_due is not None and x.days_until_due <= 7
    )
    due_in_30d_count = sum(
        1 for x in items if not x.is_overdue and x.days_until_due is not None and x.days_until_due <= 30
    )
    total_active_plans = (
        db.query(PMPlan).filter(PMPlan.is_active.is_(True)).count()
    )
    return PMReminderSummary(
        overdue_count=overdue_count,
        due_in_7d_count=due_in_7d_count,
        due_in_30d_count=due_in_30d_count,
        total_active_plans=total_active_plans,
        items=items,
    )


def recompute_next_due(db: Session, plan_id: int) -> PMPlan:
    """根据 last_executed_at + cycle_days 重算 next_due_date。

    无 last_executed_at 时回退到 created_at。不 commit（由调用者决定）。
    """
    plan = db.query(PMPlan).filter(PMPlan.id == plan_id).first()
    if plan is None:
        raise ValueError(f"PMPlan not found: {plan_id}")
    base = plan.last_executed_at or plan.created_at
    plan.next_due_date = base + timedelta(days=plan.cycle_days)
    return plan


# ---------- 定时任务执行体 ----------

def _scan_and_log_reminders() -> None:
    """每日扫描逾期及未来 7 天内到期的 PM 计划，写入 audit_log。

    - 逾期(days_until_due<0)：标记 PM_REMINDER_OVERDUE，最该报警
    - 未来 1..7 天到期：标记 PM_REMINDER
    - 当天到期(days_until_due==0)：归入 PM_REMINDER_DUE_TODAY
    使用独立 session，写完即 close。
    """
    db = SessionLocal()
    try:
        today = datetime.utcnow()
        plans = db.query(PMPlan).filter(PMPlan.is_active.is_(True)).all()
        written = 0
        for plan in plans:
            next_due = plan.next_due_date
            if next_due is None:
                continue
            days_until_due = (next_due - today).days
            if days_until_due < 0:
                action = "PM_REMINDER_OVERDUE"
                tag = "逾期"
            elif days_until_due == 0:
                action = "PM_REMINDER_DUE_TODAY"
                tag = "今日到期"
            elif days_until_due <= 7:
                action = "PM_REMINDER"
                tag = "即将到期"
            else:
                continue
            detail = (
                f"PM{tag}提醒: plan_id={plan.id}, equipment_id={plan.equipment_id}, "
                f"name={plan.name}, next_due_date={next_due.isoformat(timespec='seconds')}, "
                f"days_until_due={days_until_due}"
            )
            db.add(
                AuditLog(
                    action=action,
                    detail=detail,
                )
            )
            written += 1
        db.commit()
        logger.info("PM提醒扫描完成, 写入 %d 条 audit_log", written)
    except Exception as e:
        logger.error("PM提醒扫描失败: %s", e, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


# ---------- 调度器生命周期 ----------

def start_pm_reminder_scheduler() -> None:
    """启动 PM 提醒调度器（每天北京 8:00 扫描一次）。如已存在则跳过。"""
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone=_SCHED_TZ)
    _scheduler.start()
    _scheduler.add_job(
        _scan_and_log_reminders,
        trigger=CronTrigger.from_crontab("0 8 * * *", timezone=_SCHED_TZ),
        id=JOB_ID,
        name="PM到期提醒扫描",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )
    logger.info("PM提醒调度器已启动 (时区=Asia/Shanghai, 每日 08:00)")


def stop_pm_reminder_scheduler() -> None:
    """停止 PM 提醒调度器。"""
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("PM提醒调度器已停止")


def is_running() -> bool:
    """返回调度器是否在运行。"""
    return _scheduler is not None and _scheduler.running
