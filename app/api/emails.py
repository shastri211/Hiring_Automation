import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.email import EmailTemplate, EmailMessage
from app.models.settings import AppSettings
from app.schemas.email import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    EmailMessageResponse,
    EmailMessageGlobalResponse,
    PaginatedEmailMessageResponse,
    BulkEmailRequest
)
from app.services.email import email_service
from app.services.queue import queue_service
from app.services.candidate_directory import get_candidate_summaries

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/templates", response_model=EmailTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(template: EmailTemplateCreate, db: AsyncSession = Depends(get_db)):
    # Check if exists
    existing = await db.execute(select(EmailTemplate).where(EmailTemplate.name == template.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Template with this name already exists")
        
    db_template = EmailTemplate(
        name=template.name,
        subject=template.subject,
        body_content=template.body_content
    )
    db.add(db_template)
    await db.commit()
    await db.refresh(db_template)
    return db_template

@router.get("/templates", response_model=List[EmailTemplateResponse])
async def list_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailTemplate).order_by(EmailTemplate.name))
    return result.scalars().all()

@router.patch("/templates/{template_id}", response_model=EmailTemplateResponse)
async def update_template(template_id: int, payload: EmailTemplateUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != template.name:
        existing = await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.name == update_data["name"], EmailTemplate.id != template_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Template with this name already exists")

    for key, value in update_data.items():
        setattr(template, key, value)

    await db.commit()
    await db.refresh(template)
    return template

@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Preserve send history (EmailMessage.subject/body_content are already
    # denormalized render-time copies) - null out references before deleting,
    # in one transaction, to avoid an FK violation.
    await db.execute(
        update(EmailMessage).where(EmailMessage.template_id == template_id).values(template_id=None)
    )
    await db.execute(
        update(AppSettings)
        .where(AppSettings.shortlist_email_template_id == template_id)
        .values(shortlist_email_template_id=None)
    )
    await db.execute(
        update(AppSettings)
        .where(AppSettings.interview_scheduled_email_template_id == template_id)
        .values(interview_scheduled_email_template_id=None)
    )
    await db.delete(template)
    await db.commit()
    return None

@router.post("/jobs/{job_id}/bulk-send")
async def bulk_send_emails(job_id: int, request: BulkEmailRequest, db: AsyncSession = Depends(get_db)):
    """
    Queue emails to be sent to a list of candidates for a specific job.
    """
    try:
        queued_count = await email_service.queue_bulk_emails(
            job_id=job_id,
            resume_ids=request.resume_ids,
            template_id=request.template_id,
            queue_service=queue_service
        )
        return {"status": "success", "queued_count": queued_count}
    except ValueError as e:
        # e.g., missing template or missing dograh link
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to queue bulk emails")
        raise HTTPException(status_code=500, detail="Internal server error queueing emails")

@router.get("/messages", response_model=PaginatedEmailMessageResponse)
async def list_email_messages(
    status_filter: Optional[str] = Query(None, alias="status"),
    job_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Global, paginated email message list (needed by the Outreach dashboard)."""
    from sqlalchemy import func

    query = select(EmailMessage)
    if status_filter:
        query = query.where(EmailMessage.status == status_filter.upper())
    if job_id is not None:
        query = query.where(EmailMessage.job_id == job_id)

    count_query = select(func.count()).select_from(query.with_only_columns(EmailMessage.id).subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(EmailMessage.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    messages = (await db.execute(query)).scalars().all()

    summaries = await get_candidate_summaries(db, [m.resume_id for m in messages])

    items = []
    for msg in messages:
        summary = summaries.get(msg.resume_id, {})
        data = EmailMessageResponse.model_validate(msg).model_dump()
        data["job_title"] = summary.get("job_title")
        data["candidate_name"] = summary.get("display_name")
        items.append(EmailMessageGlobalResponse.model_validate(data))

    return PaginatedEmailMessageResponse(items=items, total=total, page=page, page_size=page_size)

@router.get("/candidates/{resume_id}", response_model=List[EmailMessageResponse])
async def get_candidate_emails(resume_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get email history for a candidate
    """
    result = await db.execute(
        select(EmailMessage)
        .where(EmailMessage.resume_id == resume_id)
        .order_by(EmailMessage.created_at.desc())
    )
    return result.scalars().all()
