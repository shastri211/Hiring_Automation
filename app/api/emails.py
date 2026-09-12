import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.email import EmailTemplate, EmailMessage
from app.schemas.email import (
    EmailTemplateCreate,
    EmailTemplateResponse,
    EmailMessageResponse,
    BulkEmailRequest
)
from app.services.email import email_service
from app.services.queue import queue_service

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
