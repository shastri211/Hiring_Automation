from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.db.session import get_db
from app.models.job import Job
from app.models.batch import ScreeningBatch
from app.models.resume import Resume
from app.schemas.resume import UploadResponse
from app.services.storage import storage_service
from app.services.queue import queue_service

router = APIRouter()

ALLOWED_CONTENT_TYPES = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]

@router.post("/upload/{job_id}", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def bulk_upload_resumes(
    job_id: int, 
    files: List[UploadFile] = File(...), 
    db: AsyncSession = Depends(get_db)
):
    # Verify Job exists
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Create ScreeningBatch
    batch = ScreeningBatch(job_id=job_id)
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    
    accepted_files = 0
    duplicate_files = 0
    invalid_files = 0
    added_resumes = []
    
    # Process files
    for file in files:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            invalid_files += 1
            continue
            
        file_hash = await storage_service.compute_hash(file)
        
        # Check duplicate
        dup_result = await db.execute(
            select(Resume).where(Resume.job_id == job_id, Resume.file_hash == file_hash)
        )
        if dup_result.scalar_one_or_none():
            duplicate_files += 1
            continue
            
        # Store file
        prefix = f"job_{job_id}/batch_{batch.id}"
        storage_key = await storage_service.save_file(file, prefix)
        
# Save metadata
        resume = Resume(
            batch_id=batch.id,
            job_id=job_id,
            filename=file.filename,
            file_hash=file_hash,
            storage_key=storage_key
        )
        db.add(resume)
        await db.flush() # flush to get resume.id
        added_resumes.append(resume.id)
        accepted_files += 1
        
    batch.total_resumes = accepted_files
    await db.commit()
    
    # Enqueue to Redis
    for r_id in added_resumes:
        await queue_service.enqueue_resume(r_id, job_id=job_id, batch_id=batch.id)
    
    return UploadResponse(
        message="Upload received and batch created",
        batch_id=batch.id,
        job_id=job_id,
        accepted_files=accepted_files,
        duplicate_files=duplicate_files,
        invalid_files=invalid_files
    )

from fastapi.responses import FileResponse
import os

@router.get("/file/{resume_id}")
async def get_resume_file(resume_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    file_path = storage_service.get_secure_path(resume.storage_key)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    return FileResponse(
        path=file_path,
        filename=resume.filename,
        media_type="application/octet-stream"
    )
