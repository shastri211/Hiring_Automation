from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.talent_pool import TalentPoolEntry
from app.models.profile import CandidateProfile
from app.schemas.talent_pool import (
    TalentPoolEntryCreate,
    TalentPoolEntryUpdate,
    TalentPoolEntryResponse,
    PaginatedTalentPoolResponse,
)
from app.services.candidate_directory import get_candidate_summaries

router = APIRouter()


def _to_response(entry: TalentPoolEntry, summary: Optional[dict] = None) -> TalentPoolEntryResponse:
    data = {
        "id": entry.id,
        "resume_id": entry.resume_id,
        "added_from_job_id": entry.added_from_job_id,
        "tags": entry.tags or [],
        "notes": entry.notes,
        "added_at": entry.added_at,
        "updated_at": entry.updated_at,
    }
    if summary:
        data.update(summary)
    return TalentPoolEntryResponse.model_validate(data)


@router.post("/", response_model=TalentPoolEntryResponse, status_code=201)
async def add_to_talent_pool(payload: TalentPoolEntryCreate, db: AsyncSession = Depends(get_db)):
    existing_result = await db.execute(
        select(TalentPoolEntry).where(TalentPoolEntry.resume_id == payload.resume_id)
    )
    entry = existing_result.scalar_one_or_none()

    if entry is not None:
        # Idempotent upsert: merge tags, never 409.
        merged_tags = sorted(set(entry.tags or []) | set(payload.tags or []))
        entry.tags = merged_tags
        if payload.notes is not None:
            entry.notes = payload.notes
        if payload.added_from_job_id is not None and entry.added_from_job_id is None:
            entry.added_from_job_id = payload.added_from_job_id
    else:
        entry = TalentPoolEntry(
            resume_id=payload.resume_id,
            added_from_job_id=payload.added_from_job_id,
            tags=sorted(set(payload.tags or [])),
            notes=payload.notes,
        )
        db.add(entry)

    try:
        await db.commit()
    except IntegrityError:
        # Race: another request inserted the same resume_id concurrently.
        await db.rollback()
        existing_result = await db.execute(
            select(TalentPoolEntry).where(TalentPoolEntry.resume_id == payload.resume_id)
        )
        entry = existing_result.scalar_one_or_none()
        if entry is None:
            raise
    else:
        await db.refresh(entry)

    summaries = await get_candidate_summaries(db, [entry.resume_id])
    return _to_response(entry, summaries.get(entry.resume_id))


@router.get("/", response_model=PaginatedTalentPoolResponse)
async def list_talent_pool(
    q: Optional[str] = Query(None, description="Search candidate name/email"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(TalentPoolEntry).outerjoin(
        CandidateProfile, CandidateProfile.resume_id == TalentPoolEntry.resume_id
    )

    if q:
        like = f"%{q}%"
        query = query.where(
            (CandidateProfile.name.ilike(like)) | (CandidateProfile.email.ilike(like))
        )

    if tag:
        query = query.where(TalentPoolEntry.tags.contains([tag]))

    count_query = select(func.count()).select_from(query.with_only_columns(TalentPoolEntry.id).subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(TalentPoolEntry.added_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    entries = result.scalars().all()

    summaries = await get_candidate_summaries(db, [e.resume_id for e in entries])
    items = [_to_response(e, summaries.get(e.resume_id)) for e in entries]

    return PaginatedTalentPoolResponse(items=items, total=total, page=page, page_size=page_size)


@router.patch("/{entry_id}", response_model=TalentPoolEntryResponse)
async def update_talent_pool_entry(
    entry_id: int, payload: TalentPoolEntryUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(TalentPoolEntry).where(TalentPoolEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Talent pool entry not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entry, key, value)

    await db.commit()
    await db.refresh(entry)

    summaries = await get_candidate_summaries(db, [entry.resume_id])
    return _to_response(entry, summaries.get(entry.resume_id))


@router.delete("/{entry_id}", status_code=204)
async def remove_from_talent_pool(entry_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TalentPoolEntry).where(TalentPoolEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Talent pool entry not found")

    await db.delete(entry)
    await db.commit()
    return None
