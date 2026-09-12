import asyncio
import logging
from typing import List, Tuple, Optional

from google import genai
from google.genai import types

from app.core.config import settings
from app.services.model_registry import model_registry, EmbeddingProfileConfig

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    pass


class EmbeddingRateLimitError(EmbeddingError):
    pass


class EmbeddingRouter:
    def __init__(self):
        self._gemini_client = None
        if settings.GEMINI_API_KEY:
            self._gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            
        self._local_model = None
        self._local_model_loaded = False

    def _get_local_model(self, model_name: str):
        if not self._local_model_loaded:
            try:
                from sentence_transformers import SentenceTransformer
                self._local_model = SentenceTransformer(model_name)
            except ImportError:
                logger.warning("sentence_transformers not installed, local fallback disabled.")
                self._local_model = None
            except Exception as e:
                logger.warning(f"Error loading local model: {e}")
                self._local_model = None
            self._local_model_loaded = True
        return self._local_model

    async def _embed_with_gemini(self, text: str, profile: EmbeddingProfileConfig) -> List[float]:
        if not self._gemini_client:
            raise EmbeddingError("Gemini client not configured")

        loop = asyncio.get_event_loop()
        
        try:
            # We use a single attempt here. Retry logic is handled by the router wrapper.
            def _call():
                return self._gemini_client.models.embed_content(
                    model=profile.model,
                    contents=text,
                    config=types.EmbedContentConfig(
                        output_dimensionality=profile.dimensions
                    )
                )
            
            response = await asyncio.wait_for(
                loop.run_in_executor(None, _call),
                timeout=30.0
            )
            
            if not response or not response.embeddings:
                raise EmbeddingError("Gemini returned empty embeddings")
                
            return response.embeddings[0].values
            
        except asyncio.TimeoutError:
            raise EmbeddingError("Gemini embedding timeout")
        except Exception as e:
            if "429" in str(e) or "Rate" in str(e) or "Quota" in str(e):
                raise EmbeddingRateLimitError(f"Gemini Rate Limit: {e}")
            raise EmbeddingError(f"Gemini error: {e}")

    async def _embed_with_local(self, text: str, profile: EmbeddingProfileConfig) -> List[float]:
        local_model = self._get_local_model(profile.model)
        if not local_model:
            raise EmbeddingError(f"Local model {profile.model} could not be loaded")
            
        loop = asyncio.get_event_loop()
        
        def _call():
            encoded = local_model.encode(text)
            return encoded.tolist() if hasattr(encoded, 'tolist') else list(encoded)
            
        try:
            vector = await loop.run_in_executor(None, _call)
            return vector
        except Exception as e:
            raise EmbeddingError(f"Local embedding failed: {e}")

    async def generate_embedding(
        self, text: str, required_profile_name: Optional[str] = None
    ) -> Tuple[List[float], EmbeddingProfileConfig]:
        """
        Generates an embedding.
        If required_profile_name is provided, it ONLY attempts that profile.
        If required_profile_name is None, it iterates through eligible profiles.
        """
        
        if required_profile_name:
            profiles_to_try = [model_registry.get_profile_by_model(required_profile_name)]
            if not profiles_to_try[0]:
                raise EmbeddingError(f"Required embedding profile '{required_profile_name}' not found in registry.")
        else:
            profiles_to_try = model_registry.get_eligible_embedding_profiles()
            
        if not profiles_to_try:
            raise EmbeddingError("No eligible embedding profiles available.")

        for profile in profiles_to_try:
            logger.info(f"Trying Embedding provider: {profile.provider}, model: {profile.model}")
            
            # Simple retry loop per provider (bounded retry)
            for attempt in range(3):
                try:
                    if profile.provider == "gemini":
                        vector = await self._embed_with_gemini(text, profile)
                    elif profile.provider == "local":
                        vector = await self._embed_with_local(text, profile)
                    else:
                        raise EmbeddingError(f"Unknown embedding provider: {profile.provider}")
                    
                    if len(vector) != profile.dimensions:
                        raise EmbeddingError(f"Dimension mismatch. Expected {profile.dimensions}, got {len(vector)}")
                        
                    logger.info(f"Observability: Embedding Provider={profile.provider}, Model={profile.model} completed successfully.")
                    return vector, profile
                    
                except EmbeddingRateLimitError as e:
                    logger.warning(f"Embedding RateLimit hit for {profile.model}: {e}")
                    if attempt == 2:
                        model_registry.mark_embedding_cooldown(profile.model)
                        break # Give up on this provider, move to next
                    await asyncio.sleep(2 ** attempt)
                    
                except Exception as e:
                    logger.warning(f"Embedding failed for {profile.model}: {e}")
                    # For non-retryable errors, immediately break and try next provider
                    if "timeout" in str(e).lower() or "50" in str(e):
                        if attempt == 2:
                            model_registry.mark_embedding_cooldown(profile.model)
                            break
                        await asyncio.sleep(2 ** attempt)
                    else:
                        break # Break retry loop

        raise EmbeddingError("All configured embedding providers failed.")

embedding_router = EmbeddingRouter()
