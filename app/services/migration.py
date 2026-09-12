import logging
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.job import Job
from app.models.resume import Resume
from app.models.profile import CandidateProfile
from app.services.embeddings import embedding_router
from app.services.vector_store import vector_store
from app.services.model_registry import model_registry

logger = logging.getLogger(__name__)


class MigrationService:
    async def migrate_job_embedding_profile(self, job_id: int):
        """
        Migrate a job and all its resumes to a new, available embedding profile.
        """
        async with AsyncSessionLocal() as session:
            # 1. Lock the job
            job_res = await session.execute(
                select(Job).where(Job.id == job_id).with_for_update(nowait=True)
            )
            job = job_res.scalar_one_or_none()
            if not job:
                logger.error(f"Migration: Job {job_id} not found.")
                return

            if job.embedding_status == "MIGRATING":
                logger.warning(f"Migration: Job {job_id} is already migrating.")
                return

            job.embedding_status = "MIGRATING"
            await session.commit()
            
            logger.info(f"Starting embedding migration for Job {job_id}")

            try:
                # 2. Select a new profile (not the current one)
                current_profile_name = job.embedding_profile
                eligible_profiles = model_registry.get_eligible_embedding_profiles()
                
                new_profile_config = None
                for profile in eligible_profiles:
                    if profile.model != current_profile_name:
                        new_profile_config = profile
                        break
                        
                if not new_profile_config:
                    raise Exception("No fallback embedding profile available for migration.")

                # 3. Re-embed Job
                new_job_embedding, actual_profile = await embedding_router.generate_embedding(
                    str(job.job_profile), 
                    required_profile_name=new_profile_config.model
                )
                
                # 4. Fetch all resumes for this job that were successfully profiled
                resume_res = await session.execute(
                    select(Resume).where(
                        Resume.job_id == job_id,
                        Resume.workflow_stage.in_(["PROFILED", "EMBEDDED"])
                    )
                )
                resumes = resume_res.scalars().all()
                
                if resumes:
                    # Create the new collection if it doesn't exist
                    await vector_store.create_collection(actual_profile.collection, actual_profile.dimensions, actual_profile.metric)
                    
                    batch_ids = []
                    batch_vectors = []
                    batch_payloads = []
                    
                    for resume in resumes:
                        # Fetch CandidateProfile to get structured data for embedding
                        prof_res = await session.execute(
                            select(CandidateProfile).where(CandidateProfile.resume_id == resume.id)
                        )
                        prof = prof_res.scalar_one_or_none()
                        
                        if not prof:
                            logger.warning(f"Migration: Resume {resume.id} has no profile, skipping.")
                            continue
                            
                        prof_dict = {
                            "name": prof.name,
                            "contact": {
                                "email": prof.email,
                                "phone": prof.phone,
                            },
                            "summary": prof.summary,
                            "total_experience_years": prof.total_experience_years,
                            "education": prof.education,
                            "experience": prof.experience,
                            "skills": prof.skills,
                            "projects": prof.projects,
                            "certifications": prof.certifications,
                            "languages": prof.languages,
                            "achievements": prof.achievements,
                        }
                        
                        profile_json = json.dumps(prof_dict)
                        # Generate embedding using the new profile
                        resume_embedding, _ = await embedding_router.generate_embedding(
                            profile_json,
                            required_profile_name=actual_profile.model
                        )
                        
                        batch_ids.append(resume.id)
                        batch_vectors.append(resume_embedding)
                        batch_payloads.append({
                            "resume_id": resume.id, 
                            "job_id": job.id, 
                            "profile": prof_dict
                        })
                        
                        # Note: we don't necessarily need to delete the old points immediately, 
                        # but we could if we wanted to clean up.
                        
                    # Add all points to new collection
                    if batch_ids:
                        await vector_store.add_points(
                            collection_name=actual_profile.collection,
                            ids=batch_ids,
                            vectors=batch_vectors,
                            payloads=batch_payloads
                        )
                
                # 5. Commit changes to Job
                job.embedding_profile = actual_profile.model
                job.embedding_status = "READY"
                await session.commit()
                logger.info(f"Successfully migrated Job {job_id} to embedding profile {actual_profile.model}")

            except Exception as e:
                logger.error(f"Migration failed for Job {job_id}: {e}")
                job.embedding_status = "FAILED"
                await session.commit()
                raise e

migration_service = MigrationService()
