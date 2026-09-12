from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, unique=True, index=True)
    
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(255), nullable=True)
    
    summary = Column(String, nullable=True)
    total_experience_years = Column(Float, nullable=True)
    
    extraction_method = Column(String(50), default="LLM_ENRICHED")
    canonical_text = Column(String, nullable=True)
    
    
    # Store complex structured data as JSONB
    education = Column(JSONB, nullable=True)
    experience = Column(JSONB, nullable=True)
    projects = Column(JSONB, nullable=True)
    skills = Column(JSONB, nullable=True)
    certifications = Column(JSONB, nullable=True)
    languages = Column(JSONB, nullable=True)
    achievements = Column(JSONB, nullable=True)
    
    resume = relationship("Resume", back_populates="profile")
