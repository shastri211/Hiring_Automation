import json
from app.schemas.profile import CandidateProfileSchema, JobProfileSchema
from app.services.llm_provider import LLMProviderFactory

class ProfilerService:
    async def profile_candidate(self, text: str) -> dict:
        if not text or not text.strip():
            raise ValueError("Cannot profile candidate: extracted text is empty.")
            
        prompt = f"""
        Extract the following information from the resume text into a structured JSON object.
        Do NOT invent or hallucinate missing information. Use null for missing fields, or empty arrays for missing lists.
        
        Resume Text:
        {text}
        
        Expected JSON Schema:
        {json.dumps(CandidateProfileSchema.model_json_schema(), indent=2)}
        """
        
        schema = CandidateProfileSchema.model_json_schema()
        return await LLMProviderFactory.generate_with_fallback(prompt, schema)

    async def profile_job(self, text: str) -> dict:
        if not text or not text.strip():
            raise ValueError("Cannot profile job: description text is empty.")
            
        prompt = f"""
        Extract the following information from the Job Description text into a structured JSON object.
        Do NOT invent or hallucinate missing information. Use null for missing fields, or empty arrays for missing lists.
        
        Job Description Text:
        {text}
        
        Expected JSON Schema:
        {json.dumps(JobProfileSchema.model_json_schema(), indent=2)}
        """
        
        schema = JobProfileSchema.model_json_schema()
        return await LLMProviderFactory.generate_with_fallback(prompt, schema)

profiler_service = ProfilerService()
