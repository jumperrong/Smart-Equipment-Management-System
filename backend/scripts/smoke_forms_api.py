"""API 冒烟自测：表单模板与记录端到端流程。跑 backend/scripts/smoke_form_forms_api.sh 或直接 python。"""
import json
import random
import string
import sys
import urllib.request as _url
import urllib.parse as _parse

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18033/api/v1"


def _rand_tag(n=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def request(method, path, data=None, token=None, return_raw=False):
    headers = {}
    body = None
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        else:
            body = data if isinstance(data, bytes) else str(data).encode()
    req = _url.Request(BASE + path, data=body, method=method, headers=headers)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with _url.urlopen(req, timeout=30) as r:
            raw = r.read()
    except _url.HTTPError as e:
        raw = e.read()
        if return_raw:
            return e.code, raw.decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code}: {raw.decode('utf-8','replace')}") from e
    if return_raw:
        return 200, raw.decode("utf-8", "replace")
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return raw.decode("utf-8", "replace")


def main():
    # 1) login
    data = _parse.urlencode({"username": "admin", "password": "admin123"}).encode()
    req = _url.Request(BASE + "/auth/login", data=data, method="POST",
                       headers={"Content-Type": "application/x-www-form-urlencoded"})
    with _url.urlopen(req, timeout=30) as r:
        tok = json.loads(r.read())["access_token"]
    print("✓ 1. Login OK")

    # 2) 找机台
    eqs = request("GET", "/equipments", token=tok)
    eid = None
    for r in eqs:
        if r.get("asset_no") == "ET-200":
            eid = r["id"]; break
    if eid is None and eqs:
        eid = eqs[0]["id"]
    if eid is None:
        raise SystemExit("× 无可用机台数据，先 seed")
    print(f"✓ 2. Equipment id={eid}")

    # 3) 创建模板
    fields = [
        {"key":"batch_no","type":"text","label":"批号","required":True,"seq":1,"placeholder":"B20260808-01"},
        {"key":"operator_name","type":"text","label":"操作员姓名","required":True,"seq":2},
        {"key":"shift","type":"select","label":"班次","required":True,"seq":3,
         "options":[{"label":"A班","value":"A"},{"label":"B班","value":"B"},{"label":"C班","value":"C"}]},
        {"key":"chamber_temp","type":"number","label":"腔室温度","required":True,"unit":"℃","min":80,"max":150,"seq":4},
        {"key":"chamber_pressure","type":"number","label":"腔室压力","required":True,"unit":"Pa","min":0.01,"max":10,"seq":5},
        {"key":"process_time","type":"number","label":"工艺时长","required":True,"unit":"分钟","min":1,"seq":8},
        {"key":"abnormal_flag","type":"boolean","label":"是否异常","required":False,"seq":11},
        {"key":"remark","type":"textarea","label":"备注","required":False,"seq":12},
    ]
    payload = {
        "name": "工艺参数记录表-API测",
        "code": f"PROC-PARAM-SMK-{_rand_tag()}",
        "category": "record",
        "equipment_id": eid,
        "description": "冒烟自测用,完成后可删除",
        "is_active": True,
        "field_schema": fields,
    }
    existing = request("GET", "/form-templates", token=tok)
    for e in existing:
        if e.get("code") == "PROC-PARAM-API-TEST":
            try:
                request("DELETE", f"/form-templates/{e['id']}", token=tok)
                print(f"  ·清理残留模板 id={e['id']}")
            except Exception:
                pass
    tpl = request("POST", "/form-templates", data=payload, token=tok)
    tpl_id = tpl["id"]
    print(f"✓ 3. 创建模板 id={tpl_id}, fields={len(tpl['field_schema'])}")

    # 4) 必填校验：故意只填 batch_no
    failed = False
    try:
        request("POST", "/form-records", data={
            "template_id": tpl_id, "equipment_id": eid,
            "batch_no": "B-ONLY", "auto_submit": True,
            "values": [{"field_key":"batch_no","field_value":"B-ONLY"}],
        }, token=tok)
    except RuntimeError:
        failed = True
    assert failed, "× 必填校验未生效！"
    print("✓ 4. 必填校验 auto_submit 缺字段触发 400")

    # 5) 正确提交 + link_process_doc=true
    rec = request("POST", "/form-records", data={
        "template_id": tpl_id, "equipment_id": eid,
        "batch_no": "B20260808-A1", "shift": "A",
        "auto_submit": True, "link_process_doc": True,
        "values": [
            {"field_key":"batch_no","field_value":"B20260808-A1"},
            {"field_key":"operator_name","field_value":"张三"},
            {"field_key":"shift","field_value":"A"},
            {"field_key":"chamber_temp","field_value":112.5},
            {"field_key":"chamber_pressure","field_value":0.85},
            {"field_key":"process_time","field_value":45},
            {"field_key":"abnormal_flag","field_value":False},
            {"field_key":"remark","field_value":"工艺正常,参数稳定"},
        ],
    }, token=tok)
    rec_id = rec["id"]
    print(f"✓ 5. 创建记录 id={rec_id}, status={rec['status']}, submitted_at={bool(rec['submitted_at'])}")
    print(f"   values={len(rec['values'])}  template_name={rec['template_name']}  equipment_name={rec.get('equipment_name')}")

    # 6) 列表中出现
    lst = request("GET", f"/form-records?batch_no=B20260808-A1", token=tok)
    assert any(r["id"]==rec_id for r in lst)
    print(f"✓ 6. /form-records 列表包含 id={rec_id}")

    # 7) process-documents 关联条目
    pd_lst = request("GET", f"/process-documents?category=record&batch_no=B20260808-A1", token=tok)
    match_pd = next((p for p in pd_lst if p.get("form_record_id") == rec_id), None)
    assert match_pd, "× 工艺记录中未找到关联条目"
    assert match_pd["stored_path"] == "", "× 结构化记录 stored_path 必须为空字符串"
    print(f"✓ 7. process_documents 关联 id={match_pd['id']}, form_record_id={match_pd['form_record_id']}")

    # 8) 详情
    det = request("GET", f"/form-records/{rec_id}", token=tok)
    assert det["status"] == "已提交" and len(det["values"]) >= 5
    print(f"✓ 8. GET 详情 OK, values={len(det['values'])}")

    # 9) Export JSON
    code, raw_json = request("GET", f"/form-records/{rec_id}/export/json", token=tok, return_raw=True)
    assert code == 200 and "腔室温度" in raw_json and len(raw_json) > 200
    print(f"✓ 9. Export JSON HTTP{code} size={len(raw_json)}B 含中文标签")

    # 10) Export CSV 带 BOM
    code, raw_csv = request("GET", f"/form-records/{rec_id}/export/csv", token=tok, return_raw=True)
    assert code == 200 and "腔室温度" in raw_csv and raw_csv.startswith("\ufeff")
    print(f"✓ 10. Export CSV HTTP{code} size={len(raw_csv)}B 带UTF-8 BOM")

    # 11) PUT 增量覆盖
    updated = request("PUT", f"/form-records/{rec_id}", data={
        "values": [
            {"field_key":"chamber_pressure","field_value":0.92},
            {"field_key":"abnormal_flag","field_value":True},
        ],
    }, token=tok)
    vd = {v["field_key"]: v["field_value"] for v in updated["values"]}
    assert vd["abnormal_flag"] is True and vd["chamber_pressure"] == 0.92
    print("✓ 11. PUT 更新 values 覆盖 OK")

    # 12) Void
    v = request("PATCH", f"/form-records/{rec_id}/void", token=tok)
    assert v["status"] == "已作废"
    print(f"✓ 12. Void status={v['status']}")

    # 13) Delete record
    dr = request("DELETE", f"/form-records/{rec_id}", token=tok)
    assert dr["removed"] == rec_id
    print(f"✓ 13. Delete 记录 OK → {dr}")

    # 14) Delete template
    dt = request("DELETE", f"/form-templates/{tpl_id}", token=tok)
    assert dt["removed"] == tpl_id
    print(f"✓ 14. Delete 模板 OK → {dt}")

    print("\n🎉 14/14 CHECKS PASSED")


if __name__ == "__main__":
    main()
