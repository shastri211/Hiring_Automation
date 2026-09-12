from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.settings import AppSettingsResponse, AppSettingsUpdate
from app.services.settings import settings_service

router = APIRouter()


@router.get("/", response_model=AppSettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    return await settings_service.get_settings(db)


@router.patch("/", response_model=AppSettingsResponse)
async def update_settings(payload: AppSettingsUpdate, db: AsyncSession = Depends(get_db)):
    patch = payload.model_dump(exclude_unset=True)
    try:
        return await settings_service.update_settings(db, patch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
