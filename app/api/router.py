from fastapi import APIRouter

from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.receipts import router as receipts_router
from app.api.routes.auth import router as auth_router
from app.api.routes.config import router as config_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(chat_router, prefix="/chat")
api_router.include_router(receipts_router, prefix="/receipts")
api_router.include_router(auth_router, prefix="/auth")
api_router.include_router(config_router, prefix="/config")


