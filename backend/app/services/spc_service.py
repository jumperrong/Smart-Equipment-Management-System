"""SPC 统计过程控制图服务。

基于 FormRecord / FormRecordValue / FormTemplate 计算 Xbar-R 控制图及过程能力指数 Cp/Cpk。
仅消费已审核（或全部）的结构化表单记录中的数值型字段，按子组大小分组聚合。
"""
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException

from app.models import FormRecord, FormRecordValue, FormTemplate
from app.schemas import SPCChartOut, SPCChartPoint


# Xbar-R 控制图系数表（n = 2..10）：(A2, D3, D4)
_SPC_COEFF: dict[int, tuple[float, float, float]] = {
    2:  (1.880, 0.000, 3.267),
    3:  (1.023, 0.000, 2.574),
    4:  (0.729, 0.000, 2.282),
    5:  (0.577, 0.000, 2.114),
    6:  (0.483, 0.000, 2.004),
    7:  (0.419, 0.076, 1.924),
    8:  (0.373, 0.136, 1.864),
    9:  (0.337, 0.184, 1.816),
    10: (0.308, 0.223, 1.777),
}


def _to_float(value: Any) -> float | None:
    """JSON 字段值转 float：兼容 int/float/str；bool/None/数组/对象等返回 None。"""
    if value is None:
        return None
    # 注意：Python 中 bool 是 int 的子类，需先排除，避免 True->1.0
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return float(s)
        except (ValueError, TypeError):
            return None
    return None


def _sample_std(values: list[float]) -> float:
    """样本标准差（ddof=1）；少于 2 个值返回 0.0。"""
    n = len(values)
    if n < 2:
        return 0.0
    m = sum(values) / n
    var = sum((x - m) ** 2 for x in values) / (n - 1)
    return var ** 0.5


def list_numeric_fields(db: Session, template_id: int | None = None) -> list[dict]:
    """返回某模板 field_schema 中 type='number' 的字段，便于前端选择 SPC 字段。"""
    if not template_id:
        return []
    template = db.query(FormTemplate).filter(FormTemplate.id == template_id).first()
    if not template:
        raise HTTPException(404, f"表单模板 id={template_id} 不存在")
    out: list[dict] = []
    for f in template.field_schema or []:
        if f.get("type") != "number":
            continue
        out.append({
            "key": f.get("key"),
            "label": f.get("label") or f.get("key"),
            "unit": f.get("unit"),
            "min": f.get("min"),
            "max": f.get("max"),
        })
    return out


def get_spc_chart(
    db: Session,
    template_id: int | None = None,
    field_key: str | None = None,
    subgroup_size: int = 5,
    limit: int = 25,
    equipment_id: int | None = None,
    only_audited: bool = True,
) -> SPCChartOut:
    """计算 Xbar-R 控制图及过程能力指数。

    数据来源：FormRecord（按 template_id/equipment_id/状态过滤）+ FormRecordValue（field_key 对应值）。
    按 subgroup_size 分组，前 N 条记录为一组，计算组均值/极差及总体控制限。
    """
    if not field_key:
        raise HTTPException(400, "field_key 不能为空")

    n_size = subgroup_size if subgroup_size and subgroup_size > 0 else 5
    # 防御性 clamp：系数表仅支持 2..10，超出时回退到 5 避免控制限静默坍缩
    if n_size < 2:
        n_size = 2
    elif n_size > 10:
        n_size = 10

    # ---- 模板/规格信息 ----
    template_name: str | None = None
    field_label: str | None = None
    spec_usl: float | None = None
    spec_lsl: float | None = None
    spec_target: float | None = None
    if template_id:
        template = db.query(FormTemplate).filter(FormTemplate.id == template_id).first()
        if not template:
            raise HTTPException(404, f"表单模板 id={template_id} 不存在")
        template_name = template.name
        for f in template.field_schema or []:
            if f.get("key") == field_key:
                field_label = f.get("label") or field_key
                fmin = _to_float(f.get("min"))
                fmax = _to_float(f.get("max"))
                # min 视为 LSL，max 视为 USL
                if f.get("min") is not None and fmin is not None:
                    spec_lsl = fmin
                if f.get("max") is not None and fmax is not None:
                    spec_usl = fmax
                ftgt = _to_float(f.get("target"))
                if f.get("target") is not None and ftgt is not None:
                    spec_target = ftgt
                break

    # ---- 查询最近 limit*subgroup_size 条记录（按 created_at 升序呈现） ----
    q = db.query(FormRecord)
    if template_id:
        q = q.filter(FormRecord.template_id == template_id)
    if equipment_id:
        q = q.filter(FormRecord.equipment_id == equipment_id)
    if only_audited:
        q = q.filter(
            or_(FormRecord.status == "已审核", FormRecord.audited.is_(True))
        )
    total = max(n_size, n_size * limit)
    records = q.order_by(FormRecord.created_at.desc()).limit(total).all()
    records.reverse()  # 升序：旧 -> 新，便于按时间分组

    # ---- 批量取每条记录的 field_key 值 ----
    record_ids = [r.id for r in records]
    value_rows: list[FormRecordValue] = []
    if record_ids:
        value_rows = (
            db.query(FormRecordValue)
            .filter(
                FormRecordValue.record_id.in_(record_ids),
                FormRecordValue.field_key == field_key,
            )
            .all()
        )
    value_by_record: dict[int, Any] = {v.record_id: v.field_value for v in value_rows}

    # ---- 按 subgroup_size 分组 ----
    points: list[SPCChartPoint] = []
    for i in range(0, len(records), n_size):
        chunk = records[i:i + n_size]
        vals: list[float] = []
        for r in chunk:
            fv = _to_float(value_by_record.get(r.id))
            if fv is None:
                continue
            vals.append(fv)
        if not vals:
            continue
        first = chunk[0]
        mean = sum(vals) / len(vals)
        rng = max(vals) - min(vals)
        points.append(SPCChartPoint(
            sample_idx=len(points) + 1,
            sample_no=first.batch_no or str(first.id),
            timestamp=first.created_at,
            values=vals,
            mean=mean,
            range=rng,
            n=len(vals),
        ))

    # ---- 控制限计算 ----
    A2, D3, D4 = _SPC_COEFF.get(n_size, (0.0, 0.0, 0.0))
    if points:
        xbarbar = sum(p.mean for p in points) / len(points)
        rbar = sum(p.range for p in points) / len(points)
    else:
        xbarbar = 0.0
        rbar = 0.0
    xbar_cl = xbarbar
    xbar_ucl = xbarbar + A2 * rbar
    xbar_lcl = xbarbar - A2 * rbar
    r_cl = rbar
    r_ucl = D4 * rbar
    r_lcl = D3 * rbar

    # ---- 总体统计 / 过程能力 ----
    all_vals = [v for p in points for v in p.values]
    if all_vals:
        mean_overall = sum(all_vals) / len(all_vals)
        std_overall = _sample_std(all_vals)
    else:
        mean_overall = 0.0
        std_overall = 0.0

    cp: float | None = None
    cpk: float | None = None
    if spec_usl is not None and spec_lsl is not None and std_overall > 0:
        cp = (spec_usl - spec_lsl) / (6 * std_overall)
        cpk = min((spec_usl - mean_overall), (mean_overall - spec_lsl)) / (3 * std_overall)

    return SPCChartOut(
        field_key=field_key,
        field_label=field_label,
        template_id=template_id,
        template_name=template_name,
        subgroup_size=n_size,
        points=points,
        xbar_cl=xbar_cl,
        xbar_ucl=xbar_ucl,
        xbar_lcl=xbar_lcl,
        r_cl=r_cl,
        r_ucl=r_ucl,
        r_lcl=r_lcl,
        spec_usl=spec_usl,
        spec_lsl=spec_lsl,
        spec_target=spec_target,
        cp=cp,
        cpk=cpk,
        mean_overall=mean_overall,
        std_overall=std_overall,
    )
