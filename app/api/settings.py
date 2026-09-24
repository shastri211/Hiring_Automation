from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.organization import Organization
from app.schemas.settings import AppSettingsResponse, AppSettingsUpdate
from app.services.settings import settings_service
from app.api.deps import get_current_user, require_admin
from app.models.user import User

router = APIRouter()


async def _response(db: AsyncSession, organization_id: int, app_settings) -> AppSettingsResponse:
    org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalar_one()
    data = AppSettingsResponse.model_validate(app_settings).model_dump()
    data["organization_name"] = org.name
    return AppSettingsResponse(**data)


@router.get("/", response_model=AppSettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Any member of the organization may read its settings."""
    app_settings = await settings_service.get_settings(db, current_user.organization_id)
    return await _response(db, current_user.organization_id, app_settings)


@router.patch("/", response_model=AppSettingsResponse)
async def update_settings(
    payload: AppSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Company settings are admin-only."""
    organization_id = current_user.organization_id
    patch = payload.model_dump(exclude_unset=True)

    organization_name = patch.pop("organization_name", None)
    if organization_name is not None:
        organization_name = organization_name.strip()
        if not organization_name or len(organization_name) > 255:
            raise HTTPException(status_code=400, detail="Organization name must be 1-255 characters.")
        org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalar_one()
        org.name = organization_name

    try:
        app_settings = await settings_service.update_settings(db, organization_id, patch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _response(db, organization_id, app_settings)
