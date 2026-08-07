from fastapi import APIRouter

from app.api.v1 import (
    auth, equipment, attachment, spare_part, inspection, work_order,
    quality, environment, personnel, asset, dashboard, dictionary, system,
    process_document,
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


@api_router.get("/health")
def health():
    return {"status": "ok", "service": "sems-api-v1"}
