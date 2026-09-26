from pydantic import BaseModel, Field
from typing import List, Optional

class ContactInfo(BaseModel):
    email: Optional[str] = Field(default=None, description="Email address of the candidate")
    phone: Optional[str] = Field(default=None, description="Phone number of the candidate")
    location: Optional[str] = Field(default=None, description="City/State/Country of residence")
    linkedin: Optional[str] = Field(default=None, description="LinkedIn profile URL")

class Education(BaseModel):
    degree: Optional[str] = Field(default=None, description="Degree obtained (e.g., BSc Computer Science)")
    institution: Optional[str] = Field(default=None, description="University or college name")
    year: Optional[str] = Field(default=None, description="Graduation year")

class Experience(BaseModel):
    role: Optional[str] = Field(default=None, description="Job title")
    company: Optional[str] = Field(default=None, description="Company name")
    duration: Optional[str] = Field(default=None, description="Duration (e.g., 2020-2022, 2 years)")
    description: Optional[str] = Field(default=None, description="Brief description of responsibilities")

class Project(BaseModel):
    name: Optional[str] = Field(default=None, description="Project name")
    description: Optional[str] = Field(default=None, description="What the project is about")
    technologies: List[str] = Field(default_factory=list, description="List of technologies used")

class CandidateProfileSchema(BaseModel):
    name: Optional[str] = Field(default=None, description="Full name of the candidate")
    contact: Optional[ContactInfo] = Field(default_factory=ContactInfo, description="Contact information")
    summary: Optional[str] = Field(default=None, description="Professional summary or objective")
    total_experience_years: Optional[float] = Field(default=None, description="Total years of professional experience as a number")
    education: List[Education] = Field(default_factory=list, description="Educational background")
    experience: List[Experience] = Field(default_factory=list, description="Work experience")
    skills: List[str] = Field(default_factory=list, description="List of technical and soft skills")
    projects: List[Project] = Field(default_factory=list, description="Notable projects")
    certifications: List[str] = Field(default_factory=list, description="List of certifications")
    languages: List[str] = Field(default_factory=list, description="List of languages spoken")
    achievements: List[str] = Field(default_factory=list, description="Notable achievements and awards")

class JobProfileSchema(BaseModel):
    title: Optional[str] = Field(default=None, description="Job title")
    role_summary: Optional[str] = Field(default=None, description="Summary of the role")
    required_skills: List[str] = Field(default_factory=list, description="Must-have technical and soft skills")
    preferred_skills: List[str] = Field(default_factory=list, description="Nice-to-have skills")
    minimum_experience_years: Optional[float] = Field(default=None, description="Minimum years of experience required")
    education_requirements: Optional[str] = Field(default=None, description="Required education level or degrees")
    responsibilities: List[str] = Field(default_factory=list, description="Key responsibilities of the role")
    requirements: List[str] = Field(default_factory=list, description="Explicit requirements or qualifications listed in the JD (e.g. required experience, certifications, tools, or other must-haves not already captured in required_skills)")
