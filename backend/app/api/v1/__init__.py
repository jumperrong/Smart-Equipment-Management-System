from fastapi import APIRouter

from app.api.v1 import (
    auth, equipment, attachment, spare_part, inspection, work_order,
    quality, environment, personnel, asset, dashboard, dictionary, system,
    process_document, form_templates, form_records, doc_no_rules,
    process_doc_qc, form_record_qc,
    safety_inspection, work_order_sla,
    knowledge_base, equipment_cost,
    equipment_lifecycle, lubrication,
    routings, production_orders, dispatches, labor_reports, process_sections,
    lots, ncrs,
    fais, spc, production_dashboard, pm_reminder, material_kits,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(equipment.router)
api_router.include_router(attachment.router)
api_router.include_router(spare_part.router)
# 设备-易损件关联路由前缀为 /equipments/{eq_id}/spare-parts，需直接挂顶层避免前缀叠加
api_router.include_router(spare_part.equipment_router)
api_router.include_router(inspection.router)
api_router.include_router(work_order.router)
api_router.include_router(quality.router)
api_router.include_router(environment.router)
api_router.include_router(personnel.router)
api_router.include_router(asset.router)
api_router.include_router(dashboard.router)
api_router.include_router(dictionary.router)
api_router.include_router(system.router)
api_router.include_router(process_document.router)
api_router.include_router(form_templates.router)
api_router.include_router(form_records.router)
api_router.include_router(doc_no_rules.router)
api_router.include_router(process_doc_qc.router)
api_router.include_router(form_record_qc.router)
api_router.include_router(safety_inspection.router)
api_router.include_router(work_order_sla.router)
api_router.include_router(knowledge_base.router)
api_router.include_router(equipment_cost.router)
api_router.include_router(equipment_lifecycle.router)
api_router.include_router(lubrication.router)
# 生产管理
api_router.include_router(routings.router)
api_router.include_router(production_orders.router)
api_router.include_router(dispatches.router)
api_router.include_router(labor_reports.router)
api_router.include_router(process_sections.router)
api_router.include_router(lots.router)
api_router.include_router(ncrs.router)
api_router.include_router(fais.router)
api_router.include_router(spc.router)
api_router.include_router(production_dashboard.router)
api_router.include_router(pm_reminder.router)
api_router.include_router(material_kits.router)


@api_router.get("/health")
def health():
    return {"status": "ok", "service": "sems-api-v1"}
