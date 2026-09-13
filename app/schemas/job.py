from pydantic import BaseModel, ConfigDict, model_validator
from typing import List, Dict, Any, Optional

class JobBase(BaseModel):
    title: str
    description: str
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    requirements: Optional[List[str]] = None
    status: Optional[str] = "ACTIVE"

class JobCreate(JobBase):
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    experience: Dict[str, Any] = {}
    education: Dict[str, Any] = {}
    hard_constraints: Dict[str, Any] = {}

class JobResponse(JobCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _populate_skills_from_job_profile(cls, values: Any) -> Any:
        """Extract required_skills / preferred_skills from the nested job_profile
        JSON column when they are not already present as top-level attributes.

        The Job ORM model stores these inside job_profile (a JSON column), not as
        dedicated columns.  from_attributes=True cannot map them automatically, so
        we pull them out here before field validation runs.
        """
        # ORM instance: access via attribute
        if hasattr(values, "__dict__") or hasattr(values, "job_profile"):
            job_profile = getattr(values, "job_profile", None) or {}
            if isinstance(job_profile, dict):
                if not getattr(values, "required_skills", None):
                    # Pydantic won't let us set attributes on the ORM object, so we
                    # convert to a dict first and patch it.
                    data = {
                        "id": getattr(values, "id", None),
                        "title": getattr(values, "title", None),
                        "description": getattr(values, "description", None),
                        "department": getattr(values, "department", None),
                        "location": getattr(values, "location", None),
                        "employment_type": getattr(values, "employment_type", None),
                        "requirements": job_profile.get("requirements", []),
                        "status": getattr(values, "status", "ACTIVE"),
                        "required_skills": job_profile.get("required_skills", []),
                        "preferred_skills": job_profile.get("preferred_skills", []),
                        "experience": job_profile.get("experience", {}),
                        "education": job_profile.get("education", {}),
                        "hard_constraints": job_profile.get("hard_constraints", {}),
                    }
                    return data
        # Already a plain dict (e.g. from test fixtures)
        if isinstance(values, dict):
            job_profile = values.get("job_profile") or {}
            if isinstance(job_profile, dict):
                values.setdefault("required_skills", job_profile.get("required_skills", []))
                values.setdefault("preferred_skills", job_profile.get("preferred_skills", []))
                if not values.get("requirements"):
                    values["requirements"] = job_profile.get("requirements", [])
        return values

