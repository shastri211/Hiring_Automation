from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.services.queue import queue_service

router = APIRouter()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    health_status = {"status": "ok", "db": "unknown", "redis": "unknown"}
    
    try:
        await db.execute(text("SELECT 1"))
        health_status["db"] = "ok"
    except Exception:
        health_status["db"] = "error"
        health_status["status"] = "error"
        
    try:
        await queue_service.redis_client.ping()
        health_status["redis"] = "ok"
    except Exception:
        health_status["redis"] = "error"
        health_status["status"] = "error"
        
    return health_status
