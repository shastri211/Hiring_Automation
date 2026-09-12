import time
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMModelConfig:
    provider: str
    model_name: str
    priority: int
    capabilities: List[str]  # e.g., ["json", "large_context"]


@dataclass
class EmbeddingProfileConfig:
    provider: str
    model: str
    dimensions: int
    metric: str
    collection: str
    task_profile: str


class ModelRegistry:
    def __init__(self):
        # In-memory cooldowns mapping model_name -> cooldown_expiry_timestamp
        self._llm_cooldowns: Dict[str, float] = {}
        self._embedding_cooldowns: Dict[str, float] = {}
        
        self.llm_models = self._load_llm_models()
        self.embedding_profiles = self._load_embedding_profiles()

    def _load_llm_models(self) -> List[LLMModelConfig]:
        """Loads LLM models from config, ordered by provider priority and internal priority."""
        models = []
        providers = [p.strip().lower() for p in settings.LLM_PROVIDER_PRIORITY.split(",") if p.strip()]
        
        for priority, provider in enumerate(providers):
            if provider == "groq" and settings.GROQ_API_KEY:
                model_names = [m.strip() for m in settings.GROQ_MODELS.split(",") if m.strip()]
                for model_name in model_names:
                    models.append(LLMModelConfig("groq", model_name, priority, ["json"]))
                    
            elif provider == "gemini" and settings.GEMINI_API_KEY:
                model_names = [m.strip() for m in settings.GEMINI_MODELS.split(",") if m.strip()]
                for model_name in model_names:
                    models.append(LLMModelConfig("gemini", model_name, priority, ["json"]))
                    
            elif provider == "openrouter" and settings.OPENROUTER_API_KEY:
                model_names = [m.strip() for m in settings.OPENROUTER_MODELS.split(",") if m.strip()]
                for model_name in model_names:
                    models.append(LLMModelConfig("openrouter", model_name, priority, ["json"]))
                    
            elif provider == "nvidia" and settings.NVIDIA_API_KEY:
                model_names = [m.strip() for m in settings.NVIDIA_MODELS.split(",") if m.strip()]
                for model_name in model_names:
                    models.append(LLMModelConfig("nvidia", model_name, priority, ["json"]))
                    
        return models

    def _load_embedding_profiles(self) -> List[EmbeddingProfileConfig]:
        """Loads embedding profiles. 
        Currently supports Gemini (primary) and Local SentenceTransformers (fallback)."""
        profiles = []
        
        # Primary Gemini Embedding
        if settings.GEMINI_API_KEY:
            profiles.append(EmbeddingProfileConfig(
                provider="gemini",
                model=settings.EMBEDDING_MODEL,
                dimensions=settings.EMBEDDING_DIMENSION,
                metric="Cosine",
                collection=settings.QDRANT_COLLECTION,
                task_profile="resume_screening"
            ))
            # V2 Profile
            profiles.append(EmbeddingProfileConfig(
                provider="gemini",
                model=settings.EMBEDDING_MODEL,
                dimensions=settings.EMBEDDING_DIMENSION,
                metric="Cosine",
                collection=settings.QDRANT_COLLECTION_V2,
                task_profile="resume_screening_v2"
            ))
            
        # Fallback Local Embedding
        profiles.append(EmbeddingProfileConfig(
            provider="local",
            model=settings.SENTENCE_TRANSFORMERS_MODEL,
            dimensions=384,  # all-MiniLM-L6-v2 dimension
            metric="Cosine",
            collection="resume_candidates_local_384",
            task_profile="resume_screening"
        ))
        # V2 Local Profile
        profiles.append(EmbeddingProfileConfig(
            provider="local",
            model=settings.SENTENCE_TRANSFORMERS_MODEL,
            dimensions=384,
            metric="Cosine",
            collection=settings.QDRANT_COLLECTION_LOCAL_V2,
            task_profile="resume_screening_v2"
        ))
        
        return profiles

    # --- LLM Registry Methods ---

    def get_eligible_llm_models(self) -> List[LLMModelConfig]:
        """Returns all LLM models not currently in cooldown."""
        now = time.time()
        eligible = []
        for model in self.llm_models:
            expiry = self._llm_cooldowns.get(model.model_name, 0)
            if now >= expiry:
                eligible.append(model)
        return eligible

    def mark_llm_cooldown(self, model_name: str):
        """Marks an LLM model as temporarily unavailable (e.g., due to 429)."""
        expiry = time.time() + settings.LLM_COOLDOWN_SECONDS
        self._llm_cooldowns[model_name] = expiry
        logger.warning(f"Model {model_name} placed on cooldown for {settings.LLM_COOLDOWN_SECONDS}s.")

    # --- Embedding Registry Methods ---

    def get_eligible_embedding_profiles(self) -> List[EmbeddingProfileConfig]:
        """Returns all embedding profiles not currently in cooldown."""
        now = time.time()
        eligible = []
        for profile in self.embedding_profiles:
            expiry = self._embedding_cooldowns.get(profile.model, 0)
            if now >= expiry:
                eligible.append(profile)
        return eligible

    def mark_embedding_cooldown(self, model_name: str):
        """Marks an embedding model as temporarily unavailable."""
        expiry = time.time() + settings.LLM_COOLDOWN_SECONDS
        self._embedding_cooldowns[model_name] = expiry
        logger.warning(f"Embedding Model {model_name} placed on cooldown for {settings.LLM_COOLDOWN_SECONDS}s.")

    def get_profile_by_model(self, model_name: str) -> Optional[EmbeddingProfileConfig]:
        for p in self.embedding_profiles:
            if p.model == model_name:
                return p
        return None

# Global Singleton
model_registry = ModelRegistry()
