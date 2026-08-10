from datetime import datetime, timedelta
from collections import defaultdict
import random

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import (
    Equipment, EquipmentStatus, EquipmentStatusLog,
    WorkOrder, WorkOrderStatus, ProductionRecord, Product,
    User, PMPlan, SparePart, SparePartMovement,
    InspectionTemplate, InspectionItem, InspectionRecord, InspectionResult,
)
from app.schemas import (
    DashboardOut, DashboardSummary,
    DashboardEquipmentItem, DashboardStatusLogItem,
    DashboardWorkOrderItem, DashboardProductionItem,
)


OPEN_WO_STATUSES = [
    WorkOrderStatus.CREATED, WorkOrderStatus.ASSIGNED,
    WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.PENDING_REVIEW,
]


def seed_demo_statuses(db: Session):
    """演示用：为设备分配各种状态，并生成状态变更日志。
    每次启动都重新分配以确保能看到不同状态筛选效果（演示模式）。
    """
    all_eqs = db.query(Equipment).order_by(Equipment.id.asc()).all()
    if not all_eqs:
        return

    # 先清空之前的演示状态日志，并把所有设备重置回 OFFLINE
    db.query(EquipmentStatusLog).delete(synchronize_session=False)
    for eq in all_eqs:
        eq.current_status = EquipmentStatus.OFFLINE
    db.flush()

    # 轮询分布：各种状态都有代表，RUN / IDLE 占比高
    status_pool = [
        EquipmentStatus.RUN, EquipmentStatus.RUN, EquipmentStatus.RUN, EquipmentStatus.RUN,
        EquipmentStatus.IDLE, EquipmentStatus.IDLE, EquipmentStatus.IDLE,
        EquipmentStatus.DOWN,
        EquipmentStatus.PM,
        EquipmentStatus.ENGINEERING,
        EquipmentStatus.PROCESS_VALIDATION,
        EquipmentStatus.OTHER,
        EquipmentStatus.OFFLINE,
    ]
    reason_codes = ["PRODUCTION", "FAULT", "SETUP", "STARVATION", "PM", "ENG", "VALIDATION", "OTHER"]
    random.seed(42)  # 可重复的演示分布

    operator = (
        db.query(User)
        .order_by(User.id.asc()).first()
    )
    operator_id = operator.id if operator else None

    now = datetime.utcnow()
    for idx, eq in enumerate(all_eqs):
        new_status = status_pool[idx % len(status_pool)]
        eq.current_status = new_status
        eq.updated_at = now - timedelta(minutes=random.randint(0, 300))

        minutes_ago = random.randint(5, 2000)
        start_time = now - timedelta(minutes=minutes_ago)
        duration = random.randint(1, minutes_ago)
        already_closed = (
            new_status in (EquipmentStatus.RUN, EquipmentStatus.IDLE)
            and idx % 5 != 0
        )
        log = EquipmentStatusLog(
            equipment_id=eq.id,
            from_status=EquipmentStatus.OFFLINE if idx % 3 == 0 else EquipmentStatus.IDLE,
            to_status=new_status,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=duration) if already_closed else None,
            duration_minutes=float(duration) if already_closed else None,
            reason_code=reason_codes[idx % len(reason_codes)],
            reason_detail={
                EquipmentStatus.DOWN: "传感器异常触发停机，等待工程师排查",
                EquipmentStatus.PM: "计划 PM：更换滤芯 / 校准",
                EquipmentStatus.ENGINEERING: "新品工艺调试中",
                EquipmentStatus.PROCESS_VALIDATION: "工艺参数验证 RUN",
                EquipmentStatus.OTHER: "其他：临时停机（需现场说明）",
            }.get(new_status),
            operator_id=operator_id,
        )
        db.add(log)
    db.commit()

    # ============================================================
    # 【修复】PM 阶段前置：为所有第一轮生成的"open 状态记录"建立映射引用，
    # 以便后续 PM 进行中时将对应的旧 open 记录关闭（确保每台设备最多 1 条 open）。
    # ============================================================
    first_open_log_map = {}  # eq_id -> EquipmentStatusLog
    for eq in all_eqs:
        first_open = (
            db.query(EquipmentStatusLog)
            .filter(
                EquipmentStatusLog.equipment_id == eq.id,
                EquipmentStatusLog.end_time.is_(None),
            )
            .order_by(EquipmentStatusLog.id.asc())  # 第一轮那条
            .first()
        )
        if first_open:
            first_open_log_map[eq.id] = first_open

    # ================ 演示数据：PM 计划 & 对应实际 PM 状态段 ================
    # 先清空旧计划（演示用，便于重复）
    db.query(PMPlan).delete(synchronize_session=False)
    db.commit()

    now = datetime.utcnow()
    # 本周周一作为锚点基点
    weekday_today = now.weekday()  # 0=Mon
    week_mon = (now - timedelta(days=weekday_today)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # PM 蓝图：(设备关键字, 计划名, 周期天, 本周第几天(0=Mon), 开始小时, 时长分钟, 维护项, 偏差模式)
    # 偏差模式：
    #   "on_time"   - 准时开始，时长正常（±10min内）
    #   "overtime"  - 准时开始，但严重超时（+60~+120min）
    #   "early"     - 提前1~3小时开始，时长接近计划
    #   "late"      - 推迟1~2小时开始，且超时
    #   "early_over"- 提前开始 且 超时
    pm_blueprints = [
        ("IM",    "离子注入机月度 PM",   30, 0, 22, 180, ["束流校准", "源体清洁", "真空度检测"],                                  "early"),
        ("ET",    "刻蚀机周度 PM",       7, 1, 23, 120, ["腔体清洁", "射频匹配校验", "气体流量校验"],                                "overtime"),
        ("Litho", "光刻机月度 PM",      30, 2, 20, 360, ["光源校准", "透镜清洁", "真空系统检查", "剂量曲线验证"],                    "overtime"),
        ("PVD",   "PVD 溅射机双周 PM",  14, 2, 19, 240, ["靶材更换", "腔体清洁", "辉光放电清洗"],                                    "early_over"),
        ("WCC",   "湿法清洗机半月 PM",  15, 2, 21, 180, ["槽液更换", "过滤芯更换", "DI 水电阻率检测"],                               "late"),
        ("COT",   "涂胶显影周度 PM",     7, 2, 22, 120, ["喷嘴清洗", "胶盘更换", "温控校验"],                                       "on_time"),
        ("CMP",   "CMP抛光机月度 PM",  30, 3, 20, 240, ["抛光垫更换", "研磨液检查", "压力头校准"],                                  "late"),
        ("RTA",   "退火炉周度 PM",       7, 4, 21, 120, ["温区校准", "气氛管路检查", "O型圈更换"],                                   "early"),
        ("DF",    "扩散炉双周 PM",     14, 4, 22, 180, ["石英管清洁", "温区校验", "气路检漏"],                                       "overtime"),
        ("OCD",   "量测机月度 PM",      30, 5, 20, 150, ["光学系统校准", "台面水平调整", "参考样片验证"],                            "on_time"),
    ]

    # 按偏差模式计算实际开始时间偏移(分钟)和实际时长额外增量(分钟)
    def _apply_variance(mode, plan_dur):
        if mode == "on_time":
            offset = random.randint(-5, 5)        # ±5min 开始
            extra = random.randint(-10, 10)       # ±10min 时长
        elif mode == "overtime":
            offset = random.randint(-5, 10)       # 基本准时
            extra = random.randint(60, 120)       # 严重超时 1~2h
        elif mode == "early":
            offset = -random.randint(60, 180)     # 提前 1~3h
            extra = random.randint(-15, 20)       # 时长正常
        elif mode == "late":
            offset = random.randint(60, 120)     # 推迟 1~2h
            extra = random.randint(30, 80)        # 还超时 30~80min
        elif mode == "early_over":
            offset = -random.randint(45, 120)     # 提前 45min~2h
            extra = random.randint(45, 90)        # 再超时 45~90min
        else:
            offset, extra = 0, 0
        # 实际时长：保证至少 20min
        actual_dur = max(20, plan_dur + extra)
        return offset, actual_dur

    for idx, (key, plan_name, cycle_days, week_day, start_hour, duration_min, items, mode) in enumerate(pm_blueprints):
        targets = [e for e in all_eqs if key in (e.name or "")]
        if not targets:
            continue
        eq = targets[0]

        # 锚定到本周指定日期
        anchor_day = week_mon + timedelta(days=week_day)

        plan = PMPlan(
            equipment_id=eq.id,
            name=plan_name,
            cycle_days=cycle_days,
            items=items,
            next_due_date=anchor_day,
            planned_start_hour=start_hour,
            planned_duration_minutes=duration_min,
            is_active=True,
        )
        db.add(plan)
        db.flush()

        # --- 实际 PM 状态日志 ---
        # 【修复】每次生成已结束的PM段后，追加一条"回到 RUN/IDLE"的收尾日志
        # 使 to_status 链条与实际 current_status 一致：
        #   - 如果设备最后被标记为RUN → 收尾用 RUN
        #   - 如果标记为IDLE → 收尾用 IDLE
        #   - 如果标记为PM（正在进行）→ 不追加（PM是open状态）
        def _status_after(eq_id):
            """根据第一轮分配的 current_status 决定 PM 结束后回到什么状态（fallback=RUN）。"""
            e = next((x for x in all_eqs if x.id == eq_id), None)
            if e and e.current_status in (EquipmentStatus.RUN, EquipmentStatus.IDLE):
                return e.current_status
            return EquipmentStatus.RUN  # 默认回到RUN

        # 1) 上一个周期：应用偏差（每种设备都给上周期也加上偏差，保证历史数据也有对比效果）
        prev_due = anchor_day - timedelta(days=cycle_days)
        pm_plan_start_1 = prev_due + timedelta(hours=start_hour)
        off_1, dur_act_1 = _apply_variance(mode, duration_min)
        pm_start_1 = pm_plan_start_1 + timedelta(minutes=off_1)
        pm_end_1 = pm_start_1 + timedelta(minutes=dur_act_1)
        detail_suffix_1 = ""
        if off_1 < -15:
            detail_suffix_1 += f"；提前 {-off_1//60}h{-off_1%60}m 进行"
        elif off_1 > 15:
            detail_suffix_1 += f"；推迟 {off_1//60}h{off_1%60}m 开始"
        if dur_act_1 - duration_min > 30:
            detail_suffix_1 += f"；超时 {dur_act_1-duration_min}m（发现 {random.choice(['密封圈老化', '备件临时更换', '参数反复校准'])}）"
        log1 = EquipmentStatusLog(
            equipment_id=eq.id,
            from_status=EquipmentStatus.IDLE,
            to_status=EquipmentStatus.PM,
            start_time=pm_start_1,
            end_time=pm_end_1,
            duration_minutes=float(dur_act_1),
            reason_code="PM",
            reason_detail=f"计划 PM 执行：{plan_name}（周期 {cycle_days}d）{detail_suffix_1}".rstrip("；"),
            operator_id=operator_id,
        )
        db.add(log1)
        # 上周期PM → 回 RUN/IDLE 收尾
        after1 = _status_after(eq.id)
        db.add(EquipmentStatusLog(
            equipment_id=eq.id,
            from_status=EquipmentStatus.PM,
            to_status=after1,
            start_time=pm_end_1,
            end_time=pm_end_1 + timedelta(minutes=1),
            duration_minutes=1.0,
            reason_code="PRODUCTION",
            reason_detail=f"{plan_name} 完成，恢复生产",
            operator_id=operator_id,
        ))

        # 2) 本周：应用偏差
        this_plan_start = anchor_day + timedelta(hours=start_hour)
        off_2, dur_act_2 = _apply_variance(mode, duration_min)
        this_pm_start = this_plan_start + timedelta(minutes=off_2)
        this_pm_plan_end = this_pm_start + timedelta(minutes=dur_act_2)
        # 构建备注，说明偏差原因
        detail_suffix_2 = ""
        if off_2 < -15:
            h, m = divmod(-off_2, 60)
            detail_suffix_2 += f"；提前 {h}h{m}m 进行（{random.choice(['前方工序空档', '订单空档提前排产', '工程师调班完成'])}）"
        elif off_2 > 15:
            h, m = divmod(off_2, 60)
            detail_suffix_2 += f"；推迟 {h}h{m}m 开始（{random.choice(['前一工单号延迟释放', '备件未到', '人员冲突'])}）"
        if dur_act_2 - duration_min > 30:
            detail_suffix_2 += f"；超时 {dur_act_2-duration_min}m（{random.choice(['发现密封圈老化需更换', '校准参数需反复调整', '真空检漏发现微漏点'])}）"
        is_running = (this_pm_start <= now < this_pm_plan_end)
        is_future = (this_pm_start > now)
        if is_running:
            eq.current_status = EquipmentStatus.PM
            # 【修复】本轮要创建 OPEN 的 PM log，先关闭第一轮残留的 OPEN，避免设备有多个 OPEN
            old_open = first_open_log_map.pop(eq.id, None)
            if old_open:
                dur_sec = max(1, int((this_pm_start - old_open.start_time).total_seconds()))
                old_open.end_time = this_pm_start
                old_open.duration_minutes = round(dur_sec / 60.0, 2)
                db.add(old_open)
        # 【修复】is_future：本周 PM 还没开始，不造状态记录（计划只存在于 PMPlan），
        # 避免生成 to_status=PM/start_time 在未来 的 OPEN 或 CLOSED 与设备实际 current_status 冲突
        if not is_future:
            log2 = EquipmentStatusLog(
                equipment_id=eq.id,
                from_status=EquipmentStatus.RUN,
                to_status=EquipmentStatus.PM,
                start_time=this_pm_start,
                end_time=None if is_running else this_pm_plan_end,
                duration_minutes=None if is_running else float(dur_act_2),
                reason_code="PM",
                reason_detail=f"本期 PM 执行：{plan_name}{detail_suffix_2}".rstrip("；"),
                operator_id=operator_id,
            )
            db.add(log2)
            # 本周PM已完成且未在进行中 → 回 RUN/IDLE 收尾
            if not is_running:
                after2 = _status_after(eq.id)
                resume_t = this_pm_plan_end
                db.add(EquipmentStatusLog(
                    equipment_id=eq.id,
                    from_status=EquipmentStatus.PM,
                    to_status=after2,
                    start_time=resume_t,
                    end_time=resume_t + timedelta(minutes=1),
                    duration_minutes=1.0,
                    reason_code="PRODUCTION",
                    reason_detail=f"本期 {plan_name} 完成，恢复生产",
                    operator_id=operator_id,
                ))

        # 3) 额外：部分设备有一条"非计划 PM"（突发维护）记录，丰富日历展示
        if week_day in (1, 4):  # 周二、周五的设备加一条突发 PM
            unplanned_start = anchor_day + timedelta(hours=start_hour - 4, minutes=30)
            if unplanned_start < now:
                unplanned_dur = random.randint(60, 150)
                unplanned_end = unplanned_start + timedelta(minutes=unplanned_dur)
                unplanned_running = (unplanned_start <= now < unplanned_end)
                if unplanned_running:
                    # 突发PM正在进行：也关闭第一轮旧OPEN，避免冲突；并标记 current_status
                    eq.current_status = EquipmentStatus.PM
                    old_open2 = first_open_log_map.pop(eq.id, None)
                    if old_open2:
                        dur_sec = max(1, int((unplanned_start - old_open2.start_time).total_seconds()))
                        old_open2.end_time = unplanned_start
                        old_open2.duration_minutes = round(dur_sec / 60.0, 2)
                        db.add(old_open2)
                # 突发 DOWN→PM（不管是否进行中都创建，进行中的 end_time=None）
                log3 = EquipmentStatusLog(
                    equipment_id=eq.id,
                    from_status=EquipmentStatus.DOWN,
                    to_status=EquipmentStatus.PM,
                    start_time=unplanned_start,
                    end_time=None if unplanned_running else unplanned_end,
                    duration_minutes=float(unplanned_dur) if not unplanned_running else None,
                    reason_code="UNPLANNED",
                    reason_detail=f"突发维护：{plan_name} 前置检修",
                    operator_id=operator_id,
                )
                db.add(log3)
                # 非进行中的突发PM：补齐 RUN→DOWN → PM→RUN/IDLE 的完整链条
                if not unplanned_running:
                    after3 = _status_after(eq.id)
                    # 先补 DOWN 的来源（时间在突发PM之前）：RUN → DOWN
                    down_start = unplanned_start - timedelta(minutes=random.randint(5, 30))
                    db.add(EquipmentStatusLog(
                        equipment_id=eq.id,
                        from_status=EquipmentStatus.RUN,
                        to_status=EquipmentStatus.DOWN,
                        start_time=down_start,
                        end_time=unplanned_start,
                        duration_minutes=float(round((unplanned_start - down_start).total_seconds() / 60, 1)),
                        reason_code="FAULT",
                        reason_detail=f"突发故障停机，触发 {plan_name} 前置检修",
                        operator_id=operator_id,
                    ))
                    # 突发PM结束 → 恢复生产
                    db.add(EquipmentStatusLog(
                        equipment_id=eq.id,
                        from_status=EquipmentStatus.PM,
                        to_status=after3,
                        start_time=unplanned_end,
                        end_time=unplanned_end + timedelta(minutes=1),
                        duration_minutes=1.0,
                        reason_code="PRODUCTION",
                        reason_detail=f"突发维护完成，恢复生产",
                        operator_id=operator_id,
                    ))
    db.commit()


def get_dashboard(db: Session, log_limit: int = 10, current_user=None) -> DashboardOut:
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)

    # 设备列表
    equipments = db.query(Equipment).filter(Equipment.is_active.is_(True)).order_by(Equipment.id.asc()).all()
    eq_ids = [e.id for e in equipments]

    # 最近生产记录（产品产量仅统计用，不展示在设备表上）
    last_prod_map = {}
    prod_name_map = {}
    if eq_ids:
        prod_rows = (
            db.query(ProductionRecord, Product.name.label("pname"))
            .outerjoin(Product, ProductionRecord.product_id == Product.id)
            .filter(ProductionRecord.equipment_id.in_(eq_ids))
            .order_by(ProductionRecord.id.desc())
            .all()
        )
        seen2 = set()
        for pr, pname in prod_rows:
            if pr.equipment_id not in seen2:
                seen2.add(pr.equipment_id)
                last_prod_map[pr.equipment_id] = pr
                prod_name_map[pr.equipment_id] = pname

    # 每台设备的"当前状态"开始时间 + 最近变更详情
    # 【修复】优先使用"进行中(open)的日志"，否则使用"to_status == current_status 的最新日志"
    # 原因：seed中会追加历史已结束的PM日志（如突发PM），id更大但to_status≠当前状态，
    # 如果直接取max(id)会导致显示的from→to与设备的current_status不一致。
    current_status_log_map = {}
    if eq_ids:
        from sqlalchemy import func as sa_func, and_, or_

        # 子查询A：每台设备的 open 日志(end_time IS NULL)——如果存在，它就是最准确的
        open_subq = (
            db.query(
                EquipmentStatusLog.equipment_id.label("eid"),
                EquipmentStatusLog.id.label("mid"),
            )
            .filter(
                EquipmentStatusLog.equipment_id.in_(eq_ids),
                EquipmentStatusLog.end_time.is_(None),
            )
            .subquery()
        )

        # 子查询B：每台设备"to_status == 设备current_status"的最新一条——作为fallback
        # 先关联 Equipment 取 current_status
        eq_status = (
            db.query(Equipment.id.label("eid"), Equipment.current_status.label("cs"))
            .filter(Equipment.id.in_(eq_ids))
            .subquery()
        )
        # 为每台设备取满足 to_status == cs 的最大 id
        matching_ids_subq = (
            db.query(
                EquipmentStatusLog.equipment_id.label("eid"),
                sa_func.max(EquipmentStatusLog.id).label("mid"),
            )
            .join(eq_status, EquipmentStatusLog.equipment_id == eq_status.c.eid)
            .filter(EquipmentStatusLog.to_status == eq_status.c.cs)
            .group_by(EquipmentStatusLog.equipment_id)
            .subquery()
        )

        # 再做一次兜底：直接 max(id)（防止上面两种都没有）
        fallback_ids_subq = (
            db.query(
                EquipmentStatusLog.equipment_id.label("eid"),
                sa_func.max(EquipmentStatusLog.id).label("mid"),
            )
            .filter(EquipmentStatusLog.equipment_id.in_(eq_ids))
            .group_by(EquipmentStatusLog.equipment_id)
            .subquery()
        )

        # 合并：优先顺序 open > matching > fallback（对每个eid取优先级最高的mid）
        # 用 UNION ALL + 每eid取最大优先级即可，简化为3次查字典合并
        def _collect(subq):
            rows = db.query(subq.c.eid, subq.c.mid).all()
            return {r.eid: r.mid for r in rows}

        open_map = _collect(open_subq)
        matching_map = _collect(matching_ids_subq)
        fallback_map = _collect(fallback_ids_subq)

        final_map = {}
        for eid in eq_ids:
            if eid in open_map:
                final_map[eid] = open_map[eid]
            elif eid in matching_map:
                final_map[eid] = matching_map[eid]
            elif eid in fallback_map:
                final_map[eid] = fallback_map[eid]
        target_ids = list(final_map.values())

        if target_ids:
            logs_and_ops = (
                db.query(EquipmentStatusLog, User.full_name.label("op_name"), User.username.label("op_uname"))
                .filter(EquipmentStatusLog.id.in_(target_ids))
                .outerjoin(User, EquipmentStatusLog.operator_id == User.id)
                .all()
            )
            for lg, op_name, op_uname in logs_and_ops:
                display_name = op_name or op_uname or None
                current_status_log_map[lg.equipment_id] = (lg, display_name)

    eq_items = []
    status_counts = defaultdict(int)
    today_good = 0
    today_defect = 0
    pm_overtime_count = 0  # PM 进行中且已超时的设备数
    import re as _re
    for e in equipments:
        status_counts[e.current_status.value] += 1
        last_pr = last_prod_map.get(e.id)
        if last_pr:
            if last_pr.start_time and last_pr.start_time >= today_start:
                today_good += last_pr.good_qty or 0
                today_defect += last_pr.defect_qty or 0

        # 计算当前状态持续时间
        cur_log, op_name = current_status_log_map.get(e.id, (None, None))
        start_time = None
        if cur_log and cur_log.to_status == e.current_status:
            start_time = cur_log.start_time
        elif cur_log:
            # 最新日志的 to_status 和 current_status 不一致，用 updated_at 兜底
            start_time = e.updated_at or e.created_at
        else:
            start_time = e.updated_at or e.created_at
        duration_sec = max(0.0, (now - start_time).total_seconds())
        duration_minutes = round(duration_sec / 60.0, 1)

        # 判断当前 PM 是否超时：
        # 1) reason_detail 中含"超时 Xm"（用于进行中且已声明的超时事件）
        # 2) 或当前 PM 持续时长超过该设备 PM Plan 计划时长+30 分钟
        if e.current_status == EquipmentStatus.PM and cur_log:
            is_ot = False
            if cur_log.reason_detail and _re.search(r"超时\s*\d+\s*m", cur_log.reason_detail):
                is_ot = True
            else:
                # 查询该设备是否有 PM Plan
                plan = db.query(PMPlan).filter(
                    PMPlan.equipment_id == e.id, PMPlan.is_active.is_(True)
                ).order_by(PMPlan.id.desc()).first()
                if plan and plan.planned_duration_minutes:
                    threshold = plan.planned_duration_minutes + 30
                    if duration_minutes > threshold:
                        is_ot = True
            if is_ot:
                pm_overtime_count += 1

        eq_items.append(DashboardEquipmentItem(
            id=e.id,
            name=e.name,
            asset_no=e.asset_no,
            factory=e.factory,
            area=e.area,
            current_status=e.current_status,
            status_start_time=start_time,
            status_duration_minutes=duration_minutes,
            last_from_status=cur_log.from_status if cur_log else None,
            last_to_status=cur_log.to_status if cur_log else None,
            last_reason_code=cur_log.reason_code if cur_log else None,
            last_reason_detail=cur_log.reason_detail if cur_log else None,
            last_operator_name=op_name,
            last_change_time=cur_log.start_time if cur_log else None,
            updated_at=e.updated_at or e.created_at,
            last_production_no=last_pr.record_no if last_pr else None,
            last_product_name=prod_name_map.get(e.id) if last_pr else None,
            last_good_qty=last_pr.good_qty if last_pr else None,
        ))

    # 状态变更日志：多拉取(上限200)以便前端按区域筛选后仍有足够数据
    # 同时合并设备 factory/area 字段供前端筛选
    logs = (
        db.query(EquipmentStatusLog)
        .order_by(EquipmentStatusLog.id.desc())
        .limit(200)
        .all()
    )
    eq_name_map = {e.id: e.name for e in equipments}
    eq_info_map = {e.id: e for e in equipments}
    log_items = []
    for lg in logs:
        eq = eq_info_map.get(lg.equipment_id)
        log_items.append(DashboardStatusLogItem(
            id=lg.id,
            equipment_id=lg.equipment_id,
            equipment_name=eq.name if eq else f"#{lg.equipment_id}",
            equipment_factory=eq.factory if eq else None,
            equipment_area=eq.area if eq else None,
            from_status=lg.from_status,
            to_status=lg.to_status,
            reason_code=lg.reason_code,
            start_time=lg.start_time,
            duration_minutes=lg.duration_minutes,
        ))
    # 返回全部拉取的日志(上限200)，前端按区域筛选后自行控制显示条数
    # log_limit 仅作为前端默认显示条数的参考，不再截断后端数据

    # 最新工单（最近8条）
    recent_wos = (
        db.query(WorkOrder)
        .order_by(WorkOrder.id.desc())
        .limit(8)
        .all()
    )
    wo_items = [
        DashboardWorkOrderItem(
            id=wo.id, order_no=wo.order_no, type=wo.type, status=wo.status,
            equipment_id=wo.equipment_id,
            equipment_name=eq_name_map.get(wo.equipment_id, f"#{wo.equipment_id}"),
            title=wo.title, created_at=wo.created_at,
        )
        for wo in recent_wos
    ]

    # 最新生产记录（最近8条）
    recent_prs = (
        db.query(ProductionRecord, Product.name.label("pname"))
        .outerjoin(Product, ProductionRecord.product_id == Product.id)
        .order_by(ProductionRecord.id.desc())
        .limit(8)
        .all()
    )
    pr_items = [
        DashboardProductionItem(
            id=pr.id, record_no=pr.record_no, equipment_id=pr.equipment_id,
            equipment_name=eq_name_map.get(pr.equipment_id, f"#{pr.equipment_id}"),
            product_name=pname,
            batch_no=pr.batch_no,
            good_qty=pr.good_qty or 0, defect_qty=pr.defect_qty or 0,
            start_time=pr.start_time, end_time=pr.end_time,
        )
        for pr, pname in recent_prs
    ]

    # 进行中工单数
    open_wo_total = (
        db.query(WorkOrder)
        .filter(WorkOrder.status.in_(OPEN_WO_STATUSES))
        .count()
    )

    # 今日生产总数（按记录数）
    today_prod_total = (
        db.query(ProductionRecord)
        .filter(ProductionRecord.start_time >= today_start)
        .count()
    )

    # OEE 简易估算（演示）：可用率 * 性能率 * 质量率
    # 可用率 = 运行设备数 / 总设备数
    # 性能率 = 今日生产合格数 / (运行设备数 * 估算理论产出) —— 演示用 0.85 兜底
    # 质量率 = 合格 / (合格 + 不合格)
    running = status_counts.get(EquipmentStatus.RUN.value, 0)
    total = len(equipments) or 1
    availability = running / total
    quality = (today_good / (today_good + today_defect)) if (today_good + today_defect) > 0 else 1.0
    performance = 0.85 if today_good > 0 else 0.0
    oee = round(availability * performance * quality * 100, 1)

    summary = DashboardSummary(
        total=len(equipments),
        running=running,
        down=status_counts.get(EquipmentStatus.DOWN.value, 0),
        idle=status_counts.get(EquipmentStatus.IDLE.value, 0),
        pm=status_counts.get(EquipmentStatus.PM.value, 0),
        pm_overtime=pm_overtime_count,
        engineering=status_counts.get(EquipmentStatus.ENGINEERING.value, 0),
        offline=status_counts.get(EquipmentStatus.OFFLINE.value, 0),
        open_work_orders=open_wo_total,
        today_production=today_prod_total,
        today_good=today_good,
        today_defect=today_defect,
        oee=oee,
    )

    # ============================================================
    # 角色相关数据填充：按 current_user.role 决定填充哪些字段
    # ============================================================
    from app.models import (
        ProcessDocument, FormRecord, FormRecordAmendment,
        SafetyInspection, LubricationPoint, KnowledgeEntry,
    )
    # role 可能是 UserRole 枚举或字符串，统一取出字符串值
    if current_user and hasattr(current_user.role, 'value'):
        role = current_user.role.value
    elif current_user and current_user.role:
        role = str(current_user.role)
    else:
        role = None
    user_id = current_user.id if current_user else None
    summary.role = role

    # 角色对应的 widget 列表（前端按 key 渲染对应区块）
    ROLE_WIDGETS = {
        "admin": [
            "kpi_admin", "equipment_status", "recent_work_orders",
            "review_overdue_docs", "low_stock_parts", "safety_alerts",
        ],
        "engineer": [
            "kpi_engineer", "equipment_status", "my_open_work_orders",
            "top_recurrence", "low_stock_parts", "safety_alerts", "lubrication_due",
        ],
        "process_engineer": [
            "kpi_process", "process_validation_equipment",
            "review_overdue_docs", "pending_review_docs",
        ],
        "qa": [
            "kpi_qa", "pending_review_docs", "review_overdue_docs",
            "safety_alerts",
        ],
        "operator": [
            "kpi_operator", "equipment_status", "my_open_work_orders",
        ],
        "viewer": [
            "kpi_viewer", "equipment_status",
        ],
    }
    role_widgets = ROLE_WIDGETS.get(role, ["kpi_viewer", "equipment_status"])

    pending_review_docs = []
    review_overdue_docs = []
    my_open_work_orders_list = []
    top_recurrence_knowledge = []
    low_stock_parts_list = []
    safety_alerts_list = []
    lubrication_due_list = []

    # ---- 文控相关：admin / qa / process_engineer ----
    if role in ("admin", "qa", "process_engineer"):
        # 待审核文档清单（status=审核中，按更新时间倒序，最多 10 条）
        pend_q = (
            db.query(ProcessDocument)
            .filter(ProcessDocument.status == "审核中")
            .order_by(ProcessDocument.updated_at.desc())
            .limit(10)
            .all()
        )
        pending_review_docs = [
            {"id": d.id, "doc_no": d.doc_no, "doc_name": d.doc_name,
             "version": d.version, "status": d.status, "updated_at": d.updated_at.isoformat() if d.updated_at else None}
            for d in pend_q
        ]
        summary.docs_pending_review = len(pend_q)
        # 待批准数（如有"待批准"状态）
        summary.docs_pending_approve = (
            db.query(ProcessDocument)
            .filter(ProcessDocument.status == "待批准")
            .count()
        )
        # 复审到期/已过期文档（next_review_date 在未来 30 天内或已过期）
        from datetime import timedelta as _td
        upcoming = now + _td(days=30)
        overdue_q = (
            db.query(ProcessDocument)
            .filter(
                ProcessDocument.status == "生效",
                ProcessDocument.next_review_date.isnot(None),
                ProcessDocument.next_review_date <= upcoming,
            )
            .order_by(ProcessDocument.next_review_date.asc())
            .limit(20)
            .all()
        )
        review_overdue_docs = [
            {"id": d.id, "doc_no": d.doc_no, "doc_name": d.doc_name,
             "version": d.version, "next_review_date": d.next_review_date.isoformat() if d.next_review_date else None,
             "is_overdue": d.next_review_date < now if d.next_review_date else False}
            for d in overdue_q
        ]
        summary.docs_review_overdue = len(overdue_q)

    # QA 专属：表单待审核数 + 附加修正待审批数
    if role == "qa":
        summary.form_records_pending_audit = (
            db.query(FormRecord)
            .filter(FormRecord.status == "已提交", FormRecord.audited.is_(False) | FormRecord.audited.is_(None))
            .count()
        )
        summary.amendments_pending = (
            db.query(FormRecordAmendment)
            .filter(FormRecordAmendment.status == "PENDING")
            .count()
        )

    # 工艺员专属：工艺验证中设备数 + 我的草稿文档数 + 我提交的工单数
    if role == "process_engineer":
        summary.process_validation_count = (
            status_counts.get(EquipmentStatus.ENGINEERING.value, 0)
            + status_counts.get(EquipmentStatus.PROCESS_VALIDATION.value, 0)
        )
        if user_id:
            summary.my_draft_docs = (
                db.query(ProcessDocument)
                .filter(ProcessDocument.status == "草稿", ProcessDocument.uploaded_by == user_id)
                .count()
            )
            summary.my_process_work_orders = (
                db.query(WorkOrder)
                .filter(WorkOrder.assignee_id == user_id)
                .count()
            )

    # ---- 工单相关：admin / engineer / operator ----
    if role in ("admin", "engineer", "operator") and user_id:
        my_wos = (
            db.query(WorkOrder)
            .filter(
                WorkOrder.assignee_id == user_id,
                WorkOrder.status.in_(OPEN_WO_STATUSES),
            )
            .order_by(WorkOrder.id.desc())
            .limit(10)
            .all()
        )
        my_open_work_orders_list = [
            {"id": wo.id, "order_no": wo.order_no, "type": wo.type.value if wo.type else None,
             "status": wo.status.value if wo.status else None,
             "title": wo.title, "equipment_id": wo.equipment_id,
             "equipment_name": eq_name_map.get(wo.equipment_id, f"#{wo.equipment_id}"),
             "created_at": wo.created_at.isoformat() if wo.created_at else None}
            for wo in my_wos
        ]
        summary.my_open_work_orders = len(my_wos)
        # SLA 违约数（assignee 是当前用户的违约工单）
        summary.sla_breached_count = (
            db.query(WorkOrder)
            .filter(
                WorkOrder.assignee_id == user_id,
                WorkOrder.sla_breached.is_(True),
            )
            .count()
        )

    # admin / engineer：全量 SLA 违约数 + 备件低库存 + 故障复发 TOP（仅 engineer）
    if role in ("admin", "engineer"):
        # 备件低库存清单
        low_q = (
            db.query(SparePart)
            .filter(SparePart.current_stock < SparePart.safety_stock)
            .order_by((SparePart.safety_stock - SparePart.current_stock).desc())
            .limit(10)
            .all()
        )
        low_stock_parts_list = [
            {"id": p.id, "sku": p.sku, "name": p.name, "spec": p.spec,
             "current_stock": p.current_stock, "safety_stock": p.safety_stock,
             "unit": p.unit, "location": p.location}
            for p in low_q
        ]
        summary.low_stock_parts = len(low_q)
        # 安全检查告警清单
        from datetime import timedelta as _td2
        upcoming2 = now + _td2(days=30)
        safe_q = (
            db.query(SafetyInspection)
            .filter(
                (SafetyInspection.next_check_date.isnot(None) & (SafetyInspection.next_check_date <= upcoming2))
                | (SafetyInspection.certificate_expiry.isnot(None) & (SafetyInspection.certificate_expiry <= upcoming2))
            )
            .order_by(SafetyInspection.next_check_date.asc())
            .limit(15)
            .all()
        )
        safety_alerts_list = [
            {"id": s.id, "equipment_id": s.equipment_id, "check_name": s.check_name,
             "check_type": s.check_type, "frequency": s.frequency,
             "next_check_date": s.next_check_date.isoformat() if s.next_check_date else None,
             "certificate_expiry": s.certificate_expiry.isoformat() if s.certificate_expiry else None,
             "result": s.result}
            for s in safe_q
        ]
        summary.safety_check_due = sum(1 for s in safe_q if s.next_check_date and s.next_check_date <= upcoming2)
        summary.safety_certificate_expiring = sum(1 for s in safe_q if s.certificate_expiry and s.certificate_expiry <= upcoming2)

    # engineer 专属：故障复发 TOP + 润滑到期
    if role == "engineer":
        top_rec_q = (
            db.query(KnowledgeEntry)
            .filter(KnowledgeEntry.recurrence_count > 0)
            .order_by(KnowledgeEntry.recurrence_count.desc())
            .limit(5)
            .all()
        )
        top_recurrence_knowledge = [
            {"id": k.id, "title": k.title, "fault_category": k.fault_category,
             "symptom": k.symptom, "recurrence_count": k.recurrence_count,
             "view_count": k.view_count}
            for k in top_rec_q
        ]
        from datetime import timedelta as _td3
        upcoming3 = now + _td3(days=7)
        lub_q = (
            db.query(LubricationPoint)
            .filter(
                LubricationPoint.next_lubricated_date.isnot(None),
                LubricationPoint.next_lubricated_date <= upcoming3,
            )
            .order_by(LubricationPoint.next_lubricated_date.asc())
            .limit(15)
            .all()
        )
        lubrication_due_list = [
            {"id": l.id, "equipment_id": l.equipment_id, "point_name": l.point_name,
             "position": l.position, "oil_type": l.oil_type,
             "next_lubricated_date": l.next_lubricated_date.isoformat() if l.next_lubricated_date else None,
             "responsible_person": l.responsible_person}
            for l in lub_q
        ]
        summary.lubrication_due = len(lub_q)

    # operator 专属：今日未提交点检设备数（演示：当前所有日检模板都未提交）
    if role == "operator":
        summary.my_inspection_pending = (
            db.query(InspectionTemplate)
            .filter(InspectionTemplate.is_active.is_(True), InspectionTemplate.frequency == "DAILY")
            .count()
        )

    return DashboardOut(
        summary=summary,
        status_counts=dict(status_counts),
        equipments=eq_items,
        recent_status_logs=log_items,
        recent_work_orders=wo_items,
        recent_production=pr_items,
        role_widgets=role_widgets,
        pending_review_docs=pending_review_docs,
        review_overdue_docs=review_overdue_docs,
        my_open_work_orders_list=my_open_work_orders_list,
        top_recurrence_knowledge=top_recurrence_knowledge,
        low_stock_parts_list=low_stock_parts_list,
        safety_alerts_list=safety_alerts_list,
        lubrication_due_list=lubrication_due_list,
    )


def seed_demo_spare_parts(db: Session):
    """演示用：生成常见备件品种、初始库存与历史出入库流水。
    仅在 spare_parts 表为空时执行，避免破坏管理员手工维护的数据。
    """
    existing = db.query(SparePart).count()
    if existing > 0:
        return

    operator = db.query(User).order_by(User.id.asc()).first()
    operator_id = operator.id if operator else None
    now = datetime.utcnow()
    random.seed(2024)

    # 备件蓝图：(sku, name, spec, brand, unit, safety_stock, init_stock, unit_price, location)
    part_blueprints = [
        # ===== 电子电气类 =====
        ("SP-PCB-001", "主控板卡 PCB-A1",        "12层板/FR-4/金手指",        "Siemens",    "块",   5,  18,  2850.0, "A区-01-03"),
        ("SP-PCB-002", "IO 接口板 PCB-B2",        "32入32出/隔离型",            "Omron",      "块",   4,   9,  1280.0, "A区-01-05"),
        ("SP-SEN-001", "光电传感器 OP-300",       "对射型/NPN/30m",             "Keyence",    "个",  10,  42,   185.0, "A区-02-01"),
        ("SP-SEN-002", "压力传感器 PX-200",       "0~1MPa / 4-20mA",            "SMC",        "个",   6,  15,   520.0, "A区-02-03"),
        ("SP-SEN-003", "温度热电偶 K-Type",       "0~1200℃ / 陶瓷保护管",       "Omega",      "支",   8,  30,    95.0, "A区-02-05"),
        ("SP-SWI-001", "电磁阀 24V 5通",          "DC24V / G1/4 / 0.7MPa",      "SMC",        "个",  12,  50,   145.0, "A区-03-02"),
        ("SP-MTR-001", "伺服电机 400W",           "1.27Nm / 3000rpm / 200V",   "Yaskawa",    "台",   2,   3,  3680.0, "A区-04-01"),
        ("SP-CAB-001", "信号电缆 10米",           "DB25 双屏蔽 / 耐弯曲",        "3M",         "根",   5,  22,   240.0, "A区-05-02"),
        ("SP-CAB-002", "动力电缆 5米",            "4x2.5mm² + 2x0.5mm² 屏蔽",   "Lapp",       "根",   3,   8,   360.0, "A区-05-04"),
        ("SP-DRV-001", "变频器 2.2kW",            "三相380V / V/F+矢量",         "Mitsubishi", "台",   2,   4,  2150.0, "A区-06-01"),
        # ===== 机械结构 / 真空类 =====
        ("SP-O-001",   "O型圈 Φ30x2",             "NBR 70A / 耐油",              "NOK",        "个",  50, 260,     3.5, "B区-01-01"),
        ("SP-O-002",   "O型圈 Φ50x3",             "FKM / 耐化学腐蚀",             "NOK",        "个",  40, 180,     8.0, "B区-01-02"),
        ("SP-VAC-001", "真空泵滤芯 3μm",          "外径120 / 接口1.5\"",         "Pfeiffer",   "支",   4,   7,   680.0, "B区-02-01"),
        ("SP-GSK-001", "主轴密封套件",            "含油封+涨圈+挡圈",             "John Crane", "套",   3,   2,  1850.0, "B区-03-01"),
        ("SP-BRG-001", "角接触轴承 7008C",        "P4 级 / 配对安装",             "NSK",        "对",   6,  14,   460.0, "B区-04-02"),
        ("SP-BRG-002", "深沟球轴承 6205ZZ",       "双铁封 / 普通级",              "NSK",        "个",  20, 120,    28.0, "B区-04-04"),
        ("SP-GEA-001", "精密联轴器 D44L50",       "膜片式 / 10Nm / 孔径φ10-φ14", "KTR",        "个",   4,   8,   920.0, "B区-05-03"),
        # ===== 气液压 / 过滤 =====
        ("SP-CYL-001", "薄型气缸 Φ20x30",         "双作用 / 磁环开关槽",          "SMC",        "个",   8,  24,   210.0, "C区-01-01"),
        ("SP-FLT-001", "空气滤芯 0.01μm",         "接口1/2\"NPT / 流量100L/min", "Parker",     "支",   6,  18,   450.0, "C区-02-02"),
        ("SP-FLT-002", "DI水滤芯 1μm PP",         "10英寸 插入式",               "Millipore",  "支",  10,  36,   180.0, "C区-02-04"),
        # ===== 耗材（通用） =====
        ("SP-WIP-001", "无尘布 9x9\"",            "Class 100 / 150片/包",         "Texwipe",    "包",  20,  96,    72.0, "D区-01-01"),
        ("SP-GLV-001", "丁腈无尘手套 M号",        "千级 / 100只/盒",              "Ansell",     "盒",  15,  48,   120.0, "D区-01-03"),
        ("SP-SWA-001", "光纤擦拭棒 1.25mm",       "2.5mm 兼容 / 50支/盒",         "Chemtronics","盒",  10,  30,   280.0, "D区-02-01"),
        ("SP-CLN-001", "IPA 异丙醇 1L",           "电子级 99.9%",                 "Baker",      "瓶",  12,  18,   110.0, "D区-03-01"),
    ]

    parts = []
    for sku, name, spec, brand, unit, safety, init_stock, price, loc in part_blueprints:
        part = SparePart(
            sku=sku, name=name, spec=spec, brand=brand, unit=unit,
            safety_stock=safety, current_stock=init_stock,
            unit_price=price, location=loc,
            remark=f"演示数据：{random.choice(['常用备品', '关键备件', '安全库存', '按需备货'])}",
        )
        db.add(part)
        db.flush()
        # 期初入库日志
        mv_init = SparePartMovement(
            spare_part_id=part.id, movement_type="IN", qty=init_stock,
            before_stock=0, after_stock=init_stock,
            ref_type="INIT", ref_id=part.id, operator_id=operator_id, remark="期初建账",
        )
        db.add(mv_init)
        parts.append(part)
    db.flush()

    # ===== 生成历史出入库流水（过去 30 天内随机发生 3~7 笔/每备件，产生"低库存"演示案例）=====
    for part in parts:
        current_stock = part.current_stock
        # 从 28 天前开始，随机生成若干笔交易
        days_ago_cursor = 28
        tx_count = random.randint(3, 7)
        for _ in range(tx_count):
            days_ago_cursor -= random.randint(1, 6)
            if days_ago_cursor <= 0:
                break
            tx_time = now - timedelta(days=days_ago_cursor, hours=random.randint(8, 20), minutes=random.randint(0, 59))
            roll = random.random()
            if roll < 0.55:
                # 工单领用：出库（模拟维修/PM消耗）
                out_qty = min(random.randint(1, max(1, current_stock // 3 + 1)), current_stock)
                if out_qty <= 0:
                    continue
                before = current_stock
                after = current_stock - out_qty
                mv = SparePartMovement(
                    spare_part_id=part.id, movement_type="OUT", qty=out_qty,
                    before_stock=before, after_stock=after,
                    ref_type="WORK_ORDER", ref_id=random.randint(1000, 1999),
                    operator_id=operator_id,
                    created_at=tx_time,
                    remark=random.choice([
                        "WO# 维修更换", "PM# 周期更换", "突发故障抢修领用",
                        "例行保养消耗", "工艺优化替换",
                    ]) + f" {random.randint(1000,9999)}",
                )
                db.add(mv)
                current_stock = after
            elif roll < 0.9:
                # 采购入库
                in_qty = random.choice([5, 10, 15, 20, 25, 30, 50])
                before = current_stock
                after = current_stock + in_qty
                mv = SparePartMovement(
                    spare_part_id=part.id, movement_type="IN", qty=in_qty,
                    before_stock=before, after_stock=after,
                    ref_type="MANUAL", operator_id=operator_id,
                    created_at=tx_time,
                    remark=f"采购入库 PO-{random.randint(2000,2999)}",
                )
                db.add(mv)
                current_stock = after
            else:
                # 库存调整（盘盈/盘亏）
                target = max(0, current_stock + random.randint(-3, 3))
                before = current_stock
                diff = abs(target - before)
                if diff == 0:
                    continue
                mv = SparePartMovement(
                    spare_part_id=part.id, movement_type="ADJUST", qty=diff,
                    before_stock=before, after_stock=target,
                    ref_type="MANUAL", operator_id=operator_id,
                    created_at=tx_time,
                    remark="月末盘点 " + ("盘盈" if target > before else "盘亏"),
                )
                db.add(mv)
                current_stock = target

        # 把"最新库存"写回到 spare_parts.current_stock
        part.current_stock = current_stock

    # ===== 故意制造几个"低于安全库存"的典型，用于演示低库存红色告警 =====
    low_stock_targets = [
        ("SP-MTR-001", 1),   # 伺服电机：仅剩 1 台，安全库存 2
        ("SP-DRV-001", 0),   # 变频器：断货，安全库存 2
        ("SP-GSK-001", 1),   # 主轴密封套件：安全库存 3
        ("SP-SEN-002", 2),   # 压力传感器：安全库存 6
        ("SP-VAC-001", 1),   # 真空泵滤芯：安全库存 4
    ]
    for sku, target_qty in low_stock_targets:
        part = next((p for p in parts if p.sku == sku), None)
        if part is None:
            continue
        before = part.current_stock
        diff = abs(target_qty - before)
        if diff == 0:
            continue
        mv = SparePartMovement(
            spare_part_id=part.id,
            movement_type="ADJUST" if True else ("OUT" if target_qty < before else "IN"),
            qty=diff,
            before_stock=before, after_stock=target_qty,
            ref_type="MANUAL", operator_id=operator_id,
            created_at=now - timedelta(hours=random.randint(1, 12)),
            remark=f"演示调整：模拟{'缺货' if target_qty == 0 else '低于安全库存'}场景",
        )
        db.add(mv)
        part.current_stock = target_qty

    db.commit()


# ================================================================
# 演示数据：半导体设备 + 点检模板 / 记录
# ================================================================

_DEMO_EQUIPMENT = [
    # (name, asset_no, factory, area, model, vendor, cycle_sec)
    ("离子注入机 IM-8",       "EQ-IM-001",  "Fab-A", "注入区", "IM-8",      "Axcelis",     45),
    ("刻蚀机 ET-200",         "EQ-ET-002",  "Fab-A", "刻蚀区", "ET-200",    "Lam Research", 35),
    ("光刻机 Litho-300",       "EQ-LT-003",  "Fab-A", "光刻区", "Litho-300", "ASML",         60),
    ("PVD 溅射机 PVD-500",    "EQ-PV-004",  "Fab-A", "成膜区", "PVD-500",   "Applied Materials", 40),
    ("湿法清洗机 WCC-200",     "EQ-WC-005",  "Fab-A", "清洗区", "WCC-200",   "DNS",          30),
    ("涂胶显影 COT-300",      "EQ-CO-006",  "Fab-A", "光刻区", "COT-300",   "TEL",          50),
    ("CMP抛光机 CMP-400",     "EQ-CM-007",  "Fab-B", "CMP区",  "CMP-400",   "Ebara",        38),
    ("退火炉 RTA-100",        "EQ-RT-008",  "Fab-B", "热处理", "RTA-100",   "Kokusai",      55),
    ("扩散炉 DF-300",          "EQ-DF-009",  "Fab-B", "热处理", "DF-300",    "Centrotherm", 120),
    ("量测机 OCD-100",         "EQ-OC-010",  "Fab-B", "量测区", "OCD-100",   "KLA",          25),
]

# 点检项目蓝图：(检查项名, 标准说明)
# 按设备关键字分组
_INSPECTION_ITEMS = {
    "IM":    [("束流稳定性", "≤±2% 漂移"), ("真空度", "≤5×10⁻⁶ Torr"), ("冷却水流量", "≥4.0 L/min"), ("源体温度", "≤80℃")],
    "ET":    [("腔体真空度", "≤1×10⁻⁵ Torr"), ("RF 功率稳定性", "≤±3%"), ("气体流量(MFC)", "设定值±5%"), ("腔体温度", "60±5℃")],
    "Litho": [("光源强度", "≥80% 额定值"), ("对准精度", "≤±5nm"), ("透镜清洁度", "无颗粒/雾化"), ("环境温湿度", "22±1℃ / 45±5%RH")],
    "PVD":   [("靶材剩余厚度", "≥3mm"), ("真空度", "≤5×10⁻⁷ Torr"), ("氩气流量", "20±2 sccm"), ("基板温度", "250±10℃")],
    "WCC":   [("DI水电阻率", "≥18 MΩ·cm"), ("化学液浓度", "规格±2%"), ("流量", "≥2.0 L/min"), ("槽液温度", "65±3℃")],
    "COT":   [("喷嘴清洁度", "无堵塞/结晶"), ("胶盘温度", "22±1℃"), ("显影液流量", "设定值±3%"), ("转速校验", "≤±1 rpm")],
    "CMP":   [("抛光垫厚度", "≥1.5mm"), ("研磨液流量", "≥150 mL/min"), ("压力头压力", "设定值±0.2 psi"), ("抛光盘转速", "≤±2 rpm")],
    "RTA":   [("温区均匀性", "≤±3℃"), ("气氛管路检漏", "≤1×10⁻⁹ cc/s"), ("温控校准", "设定值±2℃"), ("冷却水流量", "≥3.0 L/min")],
    "DF":    [("石英管清洁度", "无颗粒/异物"), ("温区校验", "≤±2℃"), ("气路检漏", "≤1×10⁻⁸ cc/s"), ("排气压力", "−0.5±0.1 kPa")],
    "OCD":   [("光学系统校准", "参考样片偏差≤0.1nm"), ("台面水平", "≤±0.02°"), ("光源稳定性", "≤±1%"), ("环境洁净度", "Class 100")],
}


def seed_demo_equipment(db: Session):
    """演示用：创建 10 台典型半导体设备。
    仅在 equipments 表为空时执行。
    """
    existing = db.query(Equipment).count()
    if existing > 0:
        return

    now = datetime.utcnow()
    for idx, (name, asset_no, factory, area, model, vendor, cycle) in enumerate(_DEMO_EQUIPMENT):
        eq = Equipment(
            name=name,
            asset_no=asset_no,
            factory=factory,
            area=area,
            model=model,
            vendor=vendor,
            theoretical_cycle=float(cycle),
            install_date=now - timedelta(days=random.randint(200, 1200)),
            current_status=EquipmentStatus.OFFLINE,
            description=f"演示设备：{vendor} {model}",
        )
        db.add(eq)
    db.commit()


def seed_demo_inspections(db: Session):
    """演示用：生成点检模板、检查项和历史点检记录。
    仅在 inspection_templates 表为空时执行。
    """
    existing = db.query(InspectionTemplate).count()
    if existing > 0:
        return

    all_eqs = db.query(Equipment).order_by(Equipment.id.asc()).all()
    if not all_eqs:
        return

    operator = db.query(User).order_by(User.id.asc()).first()
    operator_id = operator.id if operator else None
    now = datetime.utcnow()
    random.seed(2026)

    # ---- 1. 创建点检模板 + 检查项 ----
    # 蓝图：(关键字, 模板名, 频率, 描述)
    template_blueprints = [
        # 日检（每台设备）
        ("IM",    "离子注入机 日常点检",     "DAILY",   "每班开机前执行"),
        ("ET",    "刻蚀机 日常点检",         "DAILY",   "每班开机前执行"),
        ("Litho", "光刻机 日常点检",         "DAILY",   "每班开机前执行"),
        ("PVD",   "PVD溅射机 日常点检",     "DAILY",   "每班开机前执行"),
        ("WCC",   "湿法清洗机 日常点检",     "DAILY",   "每班开机前执行"),
        ("COT",   "涂胶显影 日常点检",       "DAILY",   "每班开机前执行"),
        ("CMP",   "CMP抛光机 日常点检",      "DAILY",   "每班开机前执行"),
        ("RTA",   "退火炉 日常点检",         "DAILY",   "每班开机前执行"),
        ("DF",    "扩散炉 日常点检",         "DAILY",   "每班开机前执行"),
        ("OCD",   "量测机 日常点检",         "DAILY",   "每班开机前执行"),
        # 周检（关键设备）
        ("IM",    "离子注入机 周度巡检",     "WEEKLY",  "每周一深度检查"),
        ("ET",    "刻蚀机 周度巡检",         "WEEKLY",  "每周一深度检查"),
        ("Litho", "光刻机 周度巡检",         "WEEKLY",  "每周一深度检查"),
        ("PVD",   "PVD溅射机 周度巡检",      "WEEKLY",  "每周一深度检查"),
        ("CMP",   "CMP抛光机 周度巡检",      "WEEKLY",  "每周一深度检查"),
        # 月检
        ("Litho", "光刻机 月度深度点检",     "MONTHLY", "每月1日全系统校验"),
        ("DF",    "扩散炉 月度深度点检",     "MONTHLY", "每月1日全系统校验"),
    ]

    templates = []
    for key, tpl_name, freq, desc in template_blueprints:
        targets = [e for e in all_eqs if key in (e.name or "")]
        if not targets:
            continue
        eq = targets[0]
        tpl = InspectionTemplate(
            name=tpl_name,
            equipment_id=eq.id,
            frequency=freq,
            is_active=True,
            description=desc,
        )
        db.add(tpl)
        db.flush()

        # 周检/月检追加额外检查项
        items_def = list(_INSPECTION_ITEMS.get(key, []))
        if freq == "WEEKLY":
            items_def.append(("安全联锁测试", "急停→确认设备停止"))
            items_def.append(("通信状态", "SECS/GEM 无断连"))
        elif freq == "MONTHLY":
            items_def.append(("安全联锁测试", "急停→确认设备停止"))
            items_def.append(("通信状态", "SECS/GEM 无断连"))
            items_def.append(("校准证书有效期", "在有效期内"))
            items_def.append(("易损件寿命检查", "按维护手册"))

        for seq, (item_name, standard) in enumerate(items_def):
            item = InspectionItem(
                template_id=tpl.id,
                seq=seq,
                name=item_name,
                standard=standard,
                required=True,
            )
            db.add(item)
        templates.append((tpl, eq, items_def))

    db.flush()

    # ---- 2. 生成历史点检记录（过去 7 天） ----
    ng_remarks = [
        "发现异常已通知工程师",
        "参数偏差超出规格，已调整",
        "设备报警，已重置",
        "流量偏低，已清洁管路",
        "温度漂移，已校准",
    ]
    ok_remarks = ["", "", "", "设备运行正常", "各项检查合格", ""]

    shifts = ["A", "B", "C"]
    # 给每天每班次生成日检记录
    for day_offset in range(7, 0, -1):  # 7天前到昨天
        day = now - timedelta(days=day_offset)
        for tpl, eq, items_def in templates:
            if tpl.frequency != "DAILY":
                continue
            # 每天每班次 A/B/C 各一条记录
            for shift in shifts:
                inspect_time = day.replace(
                    hour={"A": 7, "B": 15, "C": 23}[shift],
                    minute=random.randint(0, 45),
                    second=0, microsecond=0,
                ) + timedelta(minutes=random.randint(0, 30))

                # 约 12% 概率 NG（体现真实场景）
                is_ng = random.random() < 0.12

                results_data = []
                overall = "OK"
                for seq, (item_name, standard) in enumerate(items_def):
                    if is_ng and random.random() < 0.35:
                        # 该项 NG
                        result_val = random.choice([
                            f"偏低 {random.randint(5, 15)}%",
                            f"{random.randint(60, 75)}℃",
                            f"{random.uniform(0.3, 0.8):.2f} (超标)",
                            f"流量 {random.randint(15, 35)}%",
                        ])
                        results_data.append({
                            "item_name": item_name,
                            "result": "NG",
                            "value": result_val,
                            "remark": random.choice(ng_remarks),
                        })
                        overall = "NG"
                    elif random.random() < 0.05:
                        # N/A 跳检
                        results_data.append({
                            "item_name": item_name,
                            "result": "NA",
                            "value": None,
                            "remark": "本次未执行",
                        })
                    else:
                        # OK
                        ok_val = ""
                        if "≤" in standard and "%" in standard:
                            ok_val = f"{random.uniform(0.5, 1.8):.1f}%"
                        elif "≥" in standard:
                            num_part = standard.split("≥")[1].strip().split()[0]
                            try:
                                base = float(num_part.rstrip(",.℃m%"))
                                ok_val = f"{base + random.uniform(0.1, 2.0):.1f}"
                            except ValueError:
                                ok_val = ""
                        elif "±" in standard:
                            parts = standard.split("±")
                            try:
                                tolerance = float(parts[1].split()[0].rstrip("℃,nm°%rpm"))
                                ok_val = f"±{random.uniform(0.1, tolerance * 0.8):.1f}"
                            except (ValueError, IndexError):
                                ok_val = ""
                        results_data.append({
                            "item_name": item_name,
                            "result": "OK",
                            "value": ok_val,
                            "remark": random.choice(ok_remarks),
                        })

                rec = InspectionRecord(
                    template_id=tpl.id,
                    equipment_id=eq.id,
                    shift=shift,
                    inspect_time=inspect_time,
                    inspector_id=operator_id,
                    overall_result=overall,
                    remark=("发现异常项，已处理" if overall == "NG" else "日常点检完成") + f" · {shift}班",
                )
                db.add(rec)
                db.flush()

                for idx, rd in enumerate(results_data):
                    # 找到对应的 item_id
                    item_id = None
                    if idx < len(items_def):
                        matching_items = [i for i in tpl.items if i.seq == idx]
                        if matching_items:
                            item_id = matching_items[0].id
                    res = InspectionResult(
                        record_id=rec.id,
                        item_id=item_id,
                        item_name=rd["item_name"],
                        result=rd["result"],
                        value=rd["value"],
                        remark=rd["remark"],
                    )
                    db.add(res)

    # 周检记录：过去 4 周各 1 条
    for week_offset in range(4, 0, -1):
        week_day = now - timedelta(weeks=week_offset)
        for tpl, eq, items_def in templates:
            if tpl.frequency != "WEEKLY":
                continue
            inspect_time = week_day.replace(
                hour=10, minute=random.randint(0, 30), second=0, microsecond=0
            )
            is_ng = random.random() < 0.15
            results_data = []
            overall = "OK"
            for seq, (item_name, standard) in enumerate(items_def):
                if is_ng and random.random() < 0.3:
                    results_data.append({
                        "item_name": item_name, "result": "NG",
                        "value": "异常", "remark": random.choice(ng_remarks),
                    })
                    overall = "NG"
                elif random.random() < 0.08:
                    results_data.append({
                        "item_name": item_name, "result": "NA",
                        "value": None, "remark": "本次未执行",
                    })
                else:
                    results_data.append({
                        "item_name": item_name, "result": "OK",
                        "value": "合格", "remark": "",
                    })

            rec = InspectionRecord(
                template_id=tpl.id,
                equipment_id=eq.id,
                shift="A",
                inspect_time=inspect_time,
                inspector_id=operator_id,
                overall_result=overall,
                remark=("周度巡检：发现异常" if overall == "NG" else "周度巡检完成"),
            )
            db.add(rec)
            db.flush()
            for idx, rd in enumerate(results_data):
                item_id = None
                if idx < len(items_def):
                    matching_items = [i for i in tpl.items if i.seq == idx]
                    if matching_items:
                        item_id = matching_items[0].id
                res = InspectionResult(
                    record_id=rec.id,
                    item_id=item_id,
                    item_name=rd["item_name"],
                    result=rd["result"],
                    value=rd["value"],
                    remark=rd["remark"],
                )
                db.add(res)

    # 月检记录：本月 1 条
    for tpl, eq, items_def in templates:
        if tpl.frequency != "MONTHLY":
            continue
        inspect_time = now.replace(
            day=1, hour=9, minute=random.randint(0, 30), second=0, microsecond=0
        )
        is_ng = random.random() < 0.2
        results_data = []
        overall = "OK"
        for seq, (item_name, standard) in enumerate(items_def):
            if is_ng and random.random() < 0.25:
                results_data.append({
                    "item_name": item_name, "result": "NG",
                    "value": "超标", "remark": random.choice(ng_remarks),
                })
                overall = "NG"
            elif random.random() < 0.1:
                results_data.append({
                    "item_name": item_name, "result": "NA",
                    "value": None, "remark": "本次未执行",
                })
            else:
                results_data.append({
                    "item_name": item_name, "result": "OK",
                    "value": "合格", "remark": "",
                })

        rec = InspectionRecord(
            template_id=tpl.id,
            equipment_id=eq.id,
            shift="A",
            inspect_time=inspect_time,
            inspector_id=operator_id,
            overall_result=overall,
            remark=("月度深度点检：发现异常需跟踪" if overall == "NG" else "月度深度点检完成"),
        )
        db.add(rec)
        db.flush()
        for idx, rd in enumerate(results_data):
            item_id = None
            if idx < len(items_def):
                matching_items = [i for i in tpl.items if i.seq == idx]
                if matching_items:
                    item_id = matching_items[0].id
            res = InspectionResult(
                record_id=rec.id,
                item_id=item_id,
                item_name=rd["item_name"],
                result=rd["result"],
                value=rd["value"],
                remark=rd["remark"],
            )
            db.add(res)

    db.commit()
