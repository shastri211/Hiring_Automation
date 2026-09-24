from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.job import Job
from app.models.resume import Resume
from app.models.screening import ScreeningResult
from app.models.candidate import Candidate, CandidateMatchSuggestion
from app.models.application import Application
from app.models.user import User
from app.schemas.screening import (
    PaginatedGlobalScreeningResultResponse,
    GlobalScreeningResultResponse,
    ScreeningResultResponse,
    is_evaluation_failed,
)
from app.schemas.candidate import (
    CandidateResponse,
    CandidateSummary,
    CandidateNameUpdateRequest,
    CandidateMatchSuggestionResponse,
    CandidateMatchSuggestionDetailResponse,
    MergeCandidatesRequest,
    UnmergeCandidateResponse,
)
from app.services import candidate_identity
from app.services.candidate_directory import get_candidate_summaries

router = APIRouter()

@router.get("/", response_model=PaginatedGlobalScreeningResultResponse)
async def get_global_candidates(
    decision: Optional[str] = Query(None, description="SHORTLIST | REVIEW | REJECT"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # Base query joining necessary tables
    query = (
        select(
            ScreeningResult,
            Job.title.label("job_title"),
            Resume.status.label("resume_status"),
            Resume.error_message,
            Resume.id.label("resume_id"),
            Job.id.label("job_id"),
        )
        .select_from(Resume)
        .join(Job, Job.id == Resume.job_id)
        .outerjoin(ScreeningResult, (ScreeningResult.resume_id == Resume.id) & (ScreeningResult.job_id == Job.id))
    )

    if decision:
        if decision.upper() == "NULL" or decision == "":
            query = query.where(ScreeningResult.decision.is_(None))
        else:
            query = query.where(ScreeningResult.decision == decision.upper())

    # Count total
    count_query = select(func.count()).select_from(
        query.with_only_columns(Resume.id).order_by(None).subquery()
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Pagination and sorting
    query = query.order_by(ScreeningResult.score.desc().nulls_last())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    # Phase 6: one batched candidate-identity resolution (display name,
    # canonical candidate_id, applications_count) covering every resume in
    # this page - not a lookup per row.
    summaries = await get_candidate_summaries(db, [row.resume_id for row in rows])

    items = []
    for row in rows:
        screening_res = row.ScreeningResult
        job_title = row.job_title
        resume_status = row.resume_status
        error_message = row.error_message
        resume_id = row.resume_id
        job_id = row.job_id
        summary = summaries.get(resume_id, {})

        base_item = ScreeningResultResponse(
            id=screening_res.id if screening_res else None,
            job_id=job_id,
            resume_id=resume_id,
            score=screening_res.score if screening_res else None,
            semantic_score=screening_res.semantic_score if screening_res else None,
            strengths=screening_res.strengths if screening_res else None,
            gaps=screening_res.gaps if screening_res else None,
            evidence=screening_res.evidence if screening_res else None,
            decision=screening_res.decision if screening_res else None,
            notes=screening_res.notes if screening_res else None,
            created_at=screening_res.created_at if screening_res else None,
            status=resume_status,
            error_message=error_message,
            display_name=summary.get("display_name"),
            candidate_id=summary.get("candidate_id"),
            applications_count=summary.get("applications_count"),
            evaluation_failed=is_evaluation_failed(screening_res.notes if screening_res else None),
        )
        data = base_item.model_dump()
        data["job_title"] = job_title
        data["candidate_name"] = summary.get("profile_name")
        item = GlobalScreeningResultResponse.model_validate(data)
        items.append(item)

    return PaginatedGlobalScreeningResultResponse(
        items=items, total=total, page=page, page_size=page_size
    )


# --- HR name override (Phase 6) -----------------------------------------------
#
# A plain field edit on Candidate.canonical_name - not a screening decision,
# so unlike app/services/screening_audit.py there is deliberately no audit
# trail here. Once set, every one of this candidate's applications across
# every job displays it immediately (it's the top of the display_name
# fallback chain in app/services/candidate_directory.py).

@router.patch("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate_name(
    candidate_id: int,
    payload: CandidateNameUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    # Blank/whitespace-only clears the override, letting the fallback chain
    # (extracted profile name / email-derived / filename) take over again.
    new_name = (payload.canonical_name or "").strip() or None
    candidate.canonical_name = new_name

    await db.commit()
    await db.refresh(candidate)
    return candidate


# --- Candidate identity: match-suggestion review + merge/unmerge (Phase 2) ---
#
# CandidateMatchSuggestion rows are filed automatically by
# app/services/candidate_identity.py off a phone-exact match signal; they
# are never auto-merged. These endpoints are the HR review surface for
# that queue, plus a direct merge for cases HR spots outside the queue and
# an unmerge to reverse either kind of merge (both use the same reversible
# Candidate.merged_into_id redirect, so undo is lossless).

@router.get("/match-suggestions", response_model=List[CandidateMatchSuggestionDetailResponse])
async def list_match_suggestions(
    status_filter: Optional[str] = Query("PENDING", alias="status", description="PENDING | MERGED | REJECTED"),
    db: AsyncSession = Depends(get_db),
):
    query = select(CandidateMatchSuggestion).order_by(CandidateMatchSuggestion.created_at.desc())
    if status_filter:
        query = query.where(CandidateMatchSuggestion.status == status_filter.upper())
    result = await db.execute(query)
    suggestions = result.scalars().all()
    if not suggestions:
        return []

    # Everything below is batched (one query per lookup type covering every
    # suggestion on this page) rather than issued per suggestion.
    candidate_ids = {s.candidate_a_id for s in suggestions} | {s.candidate_b_id for s in suggestions}
    candidates_by_id = {
        c.id: c
        for c in (await db.execute(select(Candidate).where(Candidate.id.in_(candidate_ids)))).scalars().all()
    }

    applications_count_by_candidate_id: dict[int, int] = {}
    if candidate_ids:
        rows = (
            await db.execute(
                select(Application.candidate_id, func.count(Application.id))
                .where(Application.candidate_id.in_(candidate_ids))
                .group_by(Application.candidate_id)
            )
        ).all()
        applications_count_by_candidate_id = {cid: cnt for cid, cnt in rows}

    resume_ids = {s.resume_id for s in suggestions}
    resume_rows = (
        await db.execute(
            select(Resume.id, Resume.filename, Job.id.label("job_id"), Job.title.label("job_title"))
            .select_from(Resume)
            .join(Job, Job.id == Resume.job_id)
            .where(Resume.id.in_(resume_ids))
        )
    ).all()
    resume_context_by_id = {r.id: r for r in resume_rows}

    def _summary(candidate_id: int) -> CandidateSummary:
        candidate = candidates_by_id.get(candidate_id)
        return CandidateSummary(
            id=candidate_id,
            canonical_name=candidate.canonical_name if candidate else None,
            primary_email=candidate.primary_email if candidate else None,
            primary_phone=candidate.primary_phone if candidate else None,
            applications_count=applications_count_by_candidate_id.get(candidate_id, 0),
        )

    items = []
    for s in suggestions:
        resume_ctx = resume_context_by_id.get(s.resume_id)
        items.append(
            CandidateMatchSuggestionDetailResponse(
                id=s.id,
                resume_id=s.resume_id,
                candidate_a_id=s.candidate_a_id,
                candidate_b_id=s.candidate_b_id,
                confidence=s.confidence,
                signals=s.signals,
                status=s.status,
                reviewed_by=s.reviewed_by,
                reviewed_at=s.reviewed_at,
                created_at=s.created_at,
                candidate_a=_summary(s.candidate_a_id),
                candidate_b=_summary(s.candidate_b_id),
                resume_filename=resume_ctx.filename if resume_ctx else None,
                job_id=resume_ctx.job_id if resume_ctx else None,
                job_title=resume_ctx.job_title if resume_ctx else None,
            )
        )
    return items


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(candidate_id: int, db: AsyncSession = Depends(get_db)):
    """Read-only candidate identity + merge state - the counterpart the
    frontend needs to show "merged into X" / an Unmerge action, and to
    prefill a name-edit control, without the side effects PATCH's
    clear-on-blank semantics would have if misused for a plain read."""
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    merged_into_name = None
    if candidate.merged_into_id is not None:
        target = (
            await db.execute(select(Candidate).where(Candidate.id == candidate.merged_into_id))
        ).scalar_one_or_none()
        merged_into_name = target.canonical_name if target else None

    data = CandidateResponse.model_validate(candidate).model_dump()
    data["merged_into_name"] = merged_into_name
    return CandidateResponse.model_validate(data)


@router.post("/match-suggestions/{suggestion_id}/merge", response_model=CandidateMatchSuggestionResponse)
async def merge_match_suggestion(
    suggestion_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await candidate_identity.merge_from_suggestion(db, suggestion_id=suggestion_id, merged_by=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()

    result = await db.execute(
        select(CandidateMatchSuggestion).where(CandidateMatchSuggestion.id == suggestion_id)
    )
    return result.scalar_one()


@router.post("/match-suggestions/{suggestion_id}/reject", response_model=CandidateMatchSuggestionResponse)
async def reject_match_suggestion(
    suggestion_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        suggestion = await candidate_identity.reject_match_suggestion(
            db, suggestion_id=suggestion_id, reviewed_by=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    await db.refresh(suggestion)
    return suggestion


@router.post("/merge", status_code=status.HTTP_204_NO_CONTENT)
async def merge_candidates(
    payload: MergeCandidatesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await candidate_identity.merge_candidates(
            db,
            absorbed_id=payload.absorbed_candidate_id,
            into_id=payload.into_candidate_id,
            merged_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()


@router.post("/{candidate_id}/unmerge", response_model=UnmergeCandidateResponse)
async def unmerge_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        log = await candidate_identity.unmerge_candidate(db, absorbed_id=candidate_id, reverted_by=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    return log
