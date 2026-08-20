"""批次追溯服务（Lot + Genealogy + 流转日志）。

设计要点：
- Lot 是物料/产品批次的身份主键，从投入、流转到产出全程可追溯
- LaborReport 报工时自动产出 / 流转 lot（见 record_labor_report_lot）
- 谱系 LotGenealogy 记录上游 lot -> 下游 lot 的多对多关系（如多晶锭 lot -> 单晶锭 lot）
- NCR 评审为 SCRAP 时联动 lot 状态（见 ncr_service.review_ncr）
"""
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import (
    Lot, LotStatus, LotTransaction, LotTransactionType, LotGenealogy,
    Product, ProductionOrder, Dispatch, LaborReport, User,
)
from app.schemas import LotCreate, LotUpdate, LotTransactionCreate, LotGenealogyCreate


def _gen_lot_no(db: Session) -> str:
    """自动生成 LOT-yymmdd-xxxx"""
    today = datetime.utcnow().strftime("%y%m%d")
    prefix = f"LOT-{today}-"
    # 当天已有多少
    count = db.query(Lot).filter(Lot.lot_no.like(f"{prefix}%")).count()
    seq = count + 1
    return f"{prefix}{seq:04d}"


def list_lots(
    db: Session,
    product_id: int | None = None,
    mo_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
    skip: int = 0,
    limit: int = 50,
):
    q = db.query(Lot)
    if product_id:
        q = q.filter(Lot.product_id == product_id)
    if mo_id:
        q = q.filter(Lot.mo_id == mo_id)
    if status:
        q = q.filter(Lot.status == status)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(
            (Lot.lot_no.like(kw)) | (Lot.supplier_lot.like(kw))
        )
    return q.order_by(Lot.id.desc()).offset(skip).limit(limit).all()


def get_lot(db: Session, lot_id: int) -> Lot:
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(404, f"批次 id={lot_id} 不存在")
    return lot


def get_lot_by_no(db: Session, lot_no: str) -> Lot:
    lot = db.query(Lot).filter(Lot.lot_no == lot_no).first()
    if not lot:
        raise HTTPException(404, f"批次号 {lot_no} 不存在")
    return lot


def create_lot(
    db: Session,
    obj_in: LotCreate,
    user_id: int | None = None,
    user_name: str | None = None,
) -> Lot:
    # 校验产品
    p = db.query(Product).filter(Product.id == obj_in.product_id).first()
    if not p:
        raise HTTPException(404, f"产品 id={obj_in.product_id} 不存在")

    # 校验 MO
    mo = None
    if obj_in.mo_id:
        mo = db.query(ProductionOrder).filter(ProductionOrder.id == obj_in.mo_id).first()
        if not mo:
            raise HTTPException(404, f"生产订单 id={obj_in.mo_id} 不存在")

    # 校验派工
    if obj_in.origin_dispatch_id:
        d = db.query(Dispatch).filter(Dispatch.id == obj_in.origin_dispatch_id).first()
        if not d:
            raise HTTPException(404, f"派工 id={obj_in.origin_dispatch_id} 不存在")

    # 校验报工
    if obj_in.origin_labor_report_id:
        lr = db.query(LaborReport).filter(LaborReport.id == obj_in.origin_labor_report_id).first()
        if not lr:
            raise HTTPException(404, f"报工记录 id={obj_in.origin_labor_report_id} 不存在")

    lot_no = obj_in.lot_no or _gen_lot_no(db)
    # 唯一性兜底
    if db.query(Lot).filter(Lot.lot_no == lot_no).first():
        raise HTTPException(400, f"批次号 {lot_no} 已存在")

    lot = Lot(
        lot_no=lot_no,
        product_id=obj_in.product_id,
        qty=obj_in.qty,
        unit=p.unit,
        status=LotStatus.OPEN.value,
        source_type=obj_in.source_type or "MO_OUTPUT",
        mo_id=obj_in.mo_id,
        origin_dispatch_id=obj_in.origin_dispatch_id,
        origin_labor_report_id=obj_in.origin_labor_report_id,
        supplier_lot=obj_in.supplier_lot,
        remark=obj_in.remark,
        created_by_id=user_id,
        created_by_name=user_name,
    )
    db.add(lot)
    db.flush()

    # 若指定了 dispatch，初始化一条 RECEIVE 流转
    if obj_in.origin_dispatch_id:
        txn = LotTransaction(
            lot_id=lot.id,
            txn_type=LotTransactionType.RECEIVE.value,
            to_step_seq=None,
            dispatch_id=obj_in.origin_dispatch_id,
            in_qty=obj_in.qty,
            out_qty=obj_in.qty,
            operator_id=user_id,
            operator_name=user_name,
            txn_time=datetime.utcnow(),
            remark="批次创建-投入派工",
        )
        db.add(txn)
        lot.status = LotStatus.IN_WIP.value
        lot.current_dispatch_id = obj_in.origin_dispatch_id

    db.commit()
    db.refresh(lot)
    return lot


def update_lot(db: Session, lot: Lot, obj_in: LotUpdate) -> Lot:
    data = obj_in.model_dump(exclude_unset=True, exclude_none=True)
    new_status = data.get("status")
    if new_status and lot.status != new_status:
        # 校验状态机
        valid = {
            ("OPEN", "IN_WIP"), ("OPEN", "CLOSED"), ("OPEN", "SCRAPPED"),
            ("IN_WIP", "COMPLETED"), ("IN_WIP", "ON_HOLD"), ("IN_WIP", "SCRAPPED"),
            ("ON_HOLD", "IN_WIP"), ("ON_HOLD", "SCRAPPED"), ("ON_HOLD", "CLOSED"),
            ("COMPLETED", "CLOSED"),
        }
        if (lot.status, new_status) not in valid:
            raise HTTPException(400, f"批次状态不允许从 {lot.status} 跳转到 {new_status}")
    for k, v in data.items():
        setattr(lot, k, v)
    db.commit()
    db.refresh(lot)
    return lot


def delete_lot(db: Session, lot: Lot):
    """删除批次：仅 OPEN/CLOSED 状态可删，且无下游子批次"""
    if lot.status not in (LotStatus.OPEN.value, LotStatus.CLOSED.value):
        raise HTTPException(400, f"批次状态为 {lot.status}，不可删除（仅 OPEN/CLOSED 可删）")
    children = db.query(LotGenealogy).filter(LotGenealogy.parent_lot_id == lot.id).count()
    if children > 0:
        raise HTTPException(400, "该批次存在下游子批次（谱系），不可删除")
    db.delete(lot)
    db.commit()


# ============ 流转日志 ============

def add_transaction(
    db: Session,
    obj_in: LotTransactionCreate,
    user_id: int | None = None,
    user_name: str | None = None,
) -> LotTransaction:
    """添加一条批次流转记录，并联动 lot 状态。

    - RECEIVE: 投入，lot -> IN_WIP
    - TRANSFER: 转序，更新 current_step_seq
    - COMPLETE: 完工，lot -> COMPLETED
    - SCRAP: 报废，lot -> SCRAPPED
    - SPLIT/MERGE: 通过 from_lot_id/to_lot_id 联动谱系
    """
    lot = get_lot(db, obj_in.lot_id)
    t = obj_in.txn_type
    valid_types = {e.value for e in LotTransactionType}
    if t not in valid_types:
        raise HTTPException(400, f"未知流转类型: {t}")

    txn = LotTransaction(
        lot_id=lot.id,
        txn_type=t,
        from_step_seq=obj_in.from_step_seq,
        to_step_seq=obj_in.to_step_seq,
        dispatch_id=obj_in.dispatch_id,
        labor_report_id=obj_in.labor_report_id,
        in_qty=obj_in.in_qty,
        out_qty=obj_in.out_qty,
        defect_qty=obj_in.defect_qty,
        from_lot_id=obj_in.from_lot_id,
        to_lot_id=obj_in.to_lot_id,
        operator_id=user_id,
        operator_name=user_name,
        txn_time=datetime.utcnow(),
        remark=obj_in.remark,
    )
    db.add(txn)

    # 联动 lot 状态
    if t == LotTransactionType.RECEIVE.value:
        lot.status = LotStatus.IN_WIP.value
    elif t == LotTransactionType.TRANSFER.value:
        lot.status = LotStatus.IN_WIP.value
        if obj_in.to_step_seq is not None:
            lot.current_step_seq = obj_in.to_step_seq
        if obj_in.dispatch_id:
            lot.current_dispatch_id = obj_in.dispatch_id
    elif t == LotTransactionType.COMPLETE.value:
        lot.status = LotStatus.COMPLETED.value
    elif t == LotTransactionType.SCRAP.value:
        lot.status = LotStatus.SCRAPPED.value

    db.commit()
    db.refresh(txn)
    return txn


def list_transactions(db: Session, lot_id: int) -> list[LotTransaction]:
    return (
        db.query(LotTransaction)
        .filter(LotTransaction.lot_id == lot_id)
        .order_by(LotTransaction.id)
        .all()
    )


# ============ 谱系 ============

def link_genealogy(db: Session, obj_in: LotGenealogyCreate) -> LotGenealogy:
    """记录上游 lot -> 下游 lot 的谱系关系。"""
    parent = get_lot(db, obj_in.parent_lot_id)
    child = get_lot(db, obj_in.child_lot_id)
    if parent.id == child.id:
        raise HTTPException(400, "上游批次和下游批次不能为同一个")
    # 重复校验
    exist = (
        db.query(LotGenealogy)
        .filter(
            LotGenealogy.parent_lot_id == parent.id,
            LotGenealogy.child_lot_id == child.id,
        )
        .first()
    )
    if exist:
        raise HTTPException(400, "该谱系关系已存在")

    g = LotGenealogy(
        parent_lot_id=parent.id,
        child_lot_id=child.id,
        consume_qty=obj_in.consume_qty,
        conversion_ratio=obj_in.conversion_ratio,
        relation_type=obj_in.relation_type or "PROCESS",
        remark=obj_in.remark,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def get_ancestors(db: Session, lot_id: int, depth: int = 10) -> list[dict]:
    """递归追溯所有上游 lot（父、祖父...）。"""
    visited = set()
    result = []

    def walk(lid: int, d: int):
        if d <= 0 or lid in visited:
            return
        visited.add(lid)
        parents = (
            db.query(LotGenealogy)
            .filter(LotGenealogy.child_lot_id == lid)
            .all()
        )
        for g in parents:
            p = db.query(Lot).filter(Lot.id == g.parent_lot_id).first()
            if p:
                result.append({
                    "id": p.id,
                    "lot_no": p.lot_no,
                    "product_id": p.product_id,
                    "qty": p.qty,
                    "status": p.status,
                    "consume_qty": g.consume_qty,
                    "relation_type": g.relation_type,
                    "depth_from_target": 10 - d + 1,
                })
                walk(p.id, d - 1)

    walk(lot_id, depth)
    return result


def get_descendants(db: Session, lot_id: int, depth: int = 10) -> list[dict]:
    """递归追溯所有下游 lot（子、孙...）。"""
    visited = set()
    result = []

    def walk(lid: int, d: int):
        if d <= 0 or lid in visited:
            return
        visited.add(lid)
        children = (
            db.query(LotGenealogy)
            .filter(LotGenealogy.parent_lot_id == lid)
            .all()
        )
        for g in children:
            c = db.query(Lot).filter(Lot.id == g.child_lot_id).first()
            if c:
                result.append({
                    "id": c.id,
                    "lot_no": c.lot_no,
                    "product_id": c.product_id,
                    "qty": c.qty,
                    "status": c.status,
                    "consume_qty": g.consume_qty,
                    "relation_type": g.relation_type,
                    "depth_from_target": 10 - d + 1,
                })
                walk(c.id, d - 1)

    walk(lot_id, depth)
    return result


# ============ 报工联动 ============

def record_labor_report_lot(
    db: Session,
    labor_report: LaborReport,
    user_id: int | None = None,
    user_name: str | None = None,
) -> Lot | None:
    """报工时调用：为该报工自动创建/绑定一个产出 lot。

    场景：操作员报工 50 片合格，自动生成 LOT-yyyymmdd-xxxx 关联到 MO 和派工。
    若 dispatch 已经绑定了一个 lot（current_dispatch_id 关联），则累加 qty 并写流转日志。
    """
    dispatch = labor_report.dispatch
    if not dispatch:
        return None
    mo = dispatch.production_order
    if not mo:
        return None

    good_qty = labor_report.good_qty or 0
    if good_qty <= 0:
        return None  # 不产出合格品则不创建 lot

    # 查找该派工是否已有产出 lot
    existing = (
        db.query(Lot)
        .filter(Lot.origin_dispatch_id == dispatch.id)
        .order_by(Lot.id.desc())
        .first()
    )

    if existing:
        # 累加并写流转
        existing.qty = (existing.qty or 0) + good_qty
        txn = LotTransaction(
            lot_id=existing.id,
            txn_type=LotTransactionType.TRANSFER.value,
            from_step_seq=dispatch.step_seq,
            to_step_seq=dispatch.step_seq,
            dispatch_id=dispatch.id,
            labor_report_id=labor_report.id,
            in_qty=labor_report.input_qty or 0,
            out_qty=good_qty,
            defect_qty=labor_report.defect_qty or 0,
            operator_id=user_id,
            operator_name=user_name,
            txn_time=datetime.utcnow(),
            remark=f"报工#{labor_report.id}累加产出",
        )
        db.add(txn)
        db.commit()
        db.refresh(existing)
        return existing

    # 新建 lot
    lot_no = _gen_lot_no(db)
    p = mo.product
    lot = Lot(
        lot_no=lot_no,
        product_id=mo.product_id,
        qty=good_qty,
        unit=p.unit if p else None,
        status=LotStatus.IN_WIP.value,
        source_type="MO_OUTPUT",
        mo_id=mo.id,
        origin_dispatch_id=dispatch.id,
        origin_labor_report_id=labor_report.id,
        current_step_seq=dispatch.step_seq,
        current_dispatch_id=dispatch.id,
        created_by_id=user_id,
        created_by_name=user_name,
        remark=f"派工#{dispatch.id}报工#{labor_report.id}自动产出",
    )
    db.add(lot)
    db.flush()

    txn = LotTransaction(
        lot_id=lot.id,
        txn_type=LotTransactionType.RECEIVE.value,
        to_step_seq=dispatch.step_seq,
        dispatch_id=dispatch.id,
        labor_report_id=labor_report.id,
        in_qty=labor_report.input_qty or 0,
        out_qty=good_qty,
        defect_qty=labor_report.defect_qty or 0,
        operator_id=user_id,
        operator_name=user_name,
        txn_time=datetime.utcnow(),
        remark=f"报工#{labor_report.id}首次产出",
    )
    db.add(txn)
    db.commit()
    db.refresh(lot)
    return lot
