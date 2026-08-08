"""表单模板与记录服务层辅助函数。"""
from __future__ import annotations

from typing import Iterable, Optional

from fastapi import HTTPException

from app.models import FormTemplate


ALLOWED_FIELD_TYPES = {
    "text", "textarea", "number",
    "select", "radio",
    "date", "datetime", "time",
    "boolean",
}


def normalize_field_schema(field_schema: Iterable[dict]) -> list[dict]:
    """校验并规范化模板字段定义：

    - 排序按 seq 升序；缺 seq 填 0
    - 补默认值 required=False, placeholder=None
    - 字段 key 去重(后出现的覆盖前者)；空 key 报错
    - type 白名单校验；select/radio 必须有 options 数组
    """
    result: list[dict] = []
    seen_keys: set[str] = set()
    for idx, raw in enumerate(field_schema or []):
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail=f"字段[{idx}] 定义必须为 object")
        key = (raw.get("key") or "").strip()
        if not key:
            raise HTTPException(status_code=400, detail=f"字段[{idx}] 缺少唯一 key")
        if key in seen_keys:
            raise HTTPException(status_code=400, detail=f"字段 key 重复: {key}")
        seen_keys.add(key)
        ftype = (raw.get("type") or "text").strip().lower()
        if ftype not in ALLOWED_FIELD_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"字段[{key}] type={ftype} 非法，允许: {sorted(ALLOWED_FIELD_TYPES)}",
            )
        label = (raw.get("label") or "").strip() or key
        opts = raw.get("options")
        if ftype in ("select", "radio"):
            if not isinstance(opts, list) or not opts:
                raise HTTPException(
                    status_code=400,
                    detail=f"字段[{key}] 类型为{ftype}时必须提供非空 options=[{{label,value}}, ...]",
                )
            cleaned_opts = []
            for o in opts:
                if not isinstance(o, dict):
                    continue
                v = o.get("value")
                if v is None or v == "":
                    continue
                cleaned_opts.append({
                    "label": (o.get("label") or str(v)).strip(),
                    "value": v,
                })
            if not cleaned_opts:
                raise HTTPException(status_code=400, detail=f"字段[{key}] options 无效：至少一条带value")
            opts = cleaned_opts
        else:
            opts = None
        seq = raw.get("seq")
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
            seq = idx
        def_val = raw.get("default_value")
        placeholder = raw.get("placeholder")
        if placeholder is not None:
            placeholder = str(placeholder)[:255]
        unit = raw.get("unit")
        if unit is not None:
            unit = str(unit)[:16]
        mn = raw.get("min")
        mx = raw.get("max")
        mn = float(mn) if isinstance(mn, (int, float)) and not isinstance(mn, bool) else None
        mx = float(mx) if isinstance(mx, (int, float)) and not isinstance(mx, bool) else None
        if mn is not None and mx is not None and mn > mx:
            mn, mx = mx, mn
        required = bool(raw.get("required"))
        result.append({
            "key": key, "type": ftype, "label": label,
            "required": required, "placeholder": placeholder,
            "default_value": def_val, "options": opts,
            "unit": unit, "min": mn, "max": mx, "seq": seq,
        })
    result.sort(key=lambda f: f["seq"])
    return result


def get_template_or_404(db, template_id: int) -> FormTemplate:
    tpl = db.query(FormTemplate).filter(FormTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="表单模板不存在")
    return tpl


def sorted_fields_from_template(tpl: FormTemplate) -> list[dict]:
    """返回模板字段按 seq 排序的列表；兜底规范化。"""
    try:
        return normalize_field_schema(tpl.field_schema or [])
    except HTTPException:
        raw = tpl.field_schema or []
        raw_sorted = list(raw)
        try:
            raw_sorted.sort(key=lambda f: f.get("seq", 0))
        except Exception:
            pass
        return raw_sorted


def auto_generate_record_title(tpl_name: str, batch_no: Optional[str], prod_date_iso: Optional[str]) -> str:
    parts = [tpl_name]
    if batch_no:
        parts.append(f"批次{batch_no}")
    if prod_date_iso:
        parts.append(str(prod_date_iso)[:10])
    return " · ".join(parts)


def validate_required_fields(fields: list[dict], values_by_key: dict[str, object]) -> None:
    """提交前校验 required 字段：值为 None/空字符串/空数组视为未填。"""
    missing = []
    for f in fields:
        if not f.get("required"):
            continue
        v = values_by_key.get(f["key"])
        if v is None:
            missing.append(f["label"] or f["key"])
            continue
        if isinstance(v, str) and not v.strip():
            missing.append(f["label"] or f["key"])
            continue
        if isinstance(v, (list, dict)) and len(v) == 0:
            missing.append(f["label"] or f["key"])
            continue
    if missing:
        raise HTTPException(
            status_code=400,
            detail="以下必填字段未填写: " + "、".join(missing),
        )
