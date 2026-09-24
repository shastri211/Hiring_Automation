from pydantic import BaseModel, ConfigDict
from datetime import datetime

class ResumeResponse(BaseModel):
    id: int
    batch_id: int
    job_id: int
    filename: str
    status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class BatchResponse(BaseModel):
    id: int
    job_id: int
    status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UploadResponse(BaseModel):
    message: str
    batch_id: int
    job_id: int
    accepted_files: int
    duplicate_files: int
    invalid_files: int
    # ZIP uploads only (Phase 5): a corrupt/unreadable entry inside an
    # otherwise-valid archive. Always 0 for a request with no ZIP files.
    failed_files: int = 0
