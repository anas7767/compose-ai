from fastapi import APIRouter

from compose_ai_api.api.v1.ai_architect import router as ai_architect_router
from compose_ai_api.api.v1.auth import router as auth_router
from compose_ai_api.api.v1.building_visualization import router as building_visualization_router
from compose_ai_api.api.v1.exterior_design import router as exterior_design_router
from compose_ai_api.api.v1.floor_plan_editor import router as floor_plan_editor_router
from compose_ai_api.api.v1.floor_plans import router as floor_plans_router
from compose_ai_api.api.v1.health import router as health_router
from compose_ai_api.api.v1.plot_intelligence import router as plot_intelligence_router
from compose_ai_api.api.v1.projects import router as projects_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(projects_router)
api_router.include_router(plot_intelligence_router)
api_router.include_router(ai_architect_router)
api_router.include_router(floor_plans_router)
api_router.include_router(floor_plan_editor_router)
api_router.include_router(building_visualization_router)
api_router.include_router(exterior_design_router)
