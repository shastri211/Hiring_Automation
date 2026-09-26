import json
import re
import asyncio
import logging

import httpx
from groq import AsyncGroq
from google import genai
from google.genai import types

from app.core.config import settings
from app.services.model_registry import model_registry

# Regex to strip optional fenced-code wrappers (```json ... ``` or ``` ... ```)
# Handles: capitalisation variants, leading/trailing whitespace, extra newlines.
_FENCED_JSON_RE = re.compile(
    r'^```(?:json)?\s*\n?(.*?)\n?```\s*$',
    re.DOTALL | re.IGNORECASE,
)


def _strip_fenced_json(raw: str) -> str:
    """Remove optional markdown code-fence wrapper from an LLM JSON response."""
    stripped = raw.strip()
    m = _FENCED_JSON_RE.match(stripped)
    if m:
        return m.group(1).strip()
    return stripped

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class ConfigurationError(Exception):
    pass


class RateLimitError(LLMError):
    pass


class LLMExhaustionError(LLMError):
    """Raised when all configured LLM providers/models have been tried and all failed."""
    pass


class InvalidEvaluationResultError(LLMError):
    """Raised when a provider returned a response but the JSON payload is
    empty, malformed, or missing required evaluation fields (e.g. 'score').
    This is distinct from LLMExhaustionError: the provider itself succeeded,
    but the output is unusable.
    """
    pass


class BaseProvider:
    provider_name = "base"

    async def generate_json(self, model_name: str, prompt: str, schema: dict) -> dict:
        raise NotImplementedError


# ============================================================
# GROQ
# ============================================================
class GroqProvider(BaseProvider):
    provider_name = "groq"

    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise ConfigurationError("GROQ_API_KEY is missing")
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    async def generate_json(self, model_name: str, prompt: str, schema: dict) -> dict:
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a resume extractor and evaluator. "
                                "You must output strictly in JSON format "
                                "corresponding to the schema provided. "
                                "Do not include markdown formatting or "
                                "backticks. Always output a valid JSON object."
                            ),
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    response_format={"type": "json_object"},
                    max_completion_tokens=settings.GROQ_MAX_OUTPUT_TOKENS,
                ),
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )

            content = response.choices[0].message.content
            if not content:
                raise LLMError("Groq returned empty content")

            result = json.loads(_strip_fenced_json(content))
            logger.info("LLM Provider=%s Model=%s completed successfully", self.provider_name, model_name)
            return result

        except asyncio.TimeoutError:
            raise LLMError("Groq timeout")
        except Exception as e:
            if "404" in str(e) and "model_not_found" in str(e):
                raise LLMError(f"Groq Configuration Error: model {model_name} not found")
            if "429" in str(e) or "Rate limit" in str(e):
                raise RateLimitError(f"Groq Rate Limit: {e}")
            raise LLMError(f"Groq error: {e}")


# ============================================================
# GEMINI
# ============================================================
class GeminiProvider(BaseProvider):
    provider_name = "gemini"

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ConfigurationError("GEMINI_API_KEY is missing")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def generate_json(self, model_name: str, prompt: str, schema: dict) -> dict:
        try:
            loop = asyncio.get_event_loop()

            def _call():
                return self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0.0,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )

            response = await asyncio.wait_for(
                loop.run_in_executor(None, _call),
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )

            if not response.text:
                return {}

            result = json.loads(response.text)
            logger.info("LLM Provider=%s Model=%s completed successfully", self.provider_name, model_name)
            return result

        except asyncio.TimeoutError:
            raise LLMError("Gemini timeout")
        except Exception as e:
            if "429" in str(e):
                raise RateLimitError(f"Gemini Rate Limit: {e}")
            raise LLMError(f"Gemini error: {e}")


# ============================================================
# OPENROUTER
# ============================================================
class OpenRouterProvider(BaseProvider):
    provider_name = "openrouter"

    def __init__(self):
        if not settings.OPENROUTER_API_KEY:
            raise ConfigurationError("OPENROUTER_API_KEY is missing")

    async def generate_json(self, model_name: str, prompt: str, schema: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Resume Screener",
        }

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert technical recruiter "
                        "and resume evaluator. "
                        "Return only valid JSON. "
                        "Do not return markdown or explanations. "
                        "Follow the requested schema exactly."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        timeout = httpx.Timeout(connect=10.0, read=settings.LLM_TIMEOUT_SECONDS, write=10.0, pool=10.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )

            if response.status_code == 429:
                raise RateLimitError("OpenRouter rate limit")
            if response.status_code == 400:
                # 400 = bad request / schema error — not a transient failure, do not retry
                raise LLMError(f"OpenRouter HTTP 400 (non-retryable): {response.text[:500]}")
            if response.status_code >= 500:
                raise LLMError(f"OpenRouter HTTP {response.status_code} (transient): {response.text[:200]}")
            if response.status_code >= 400:
                raise LLMError(f"OpenRouter HTTP {response.status_code}: {response.text[:500]}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMError("OpenRouter returned no choices")

            content = choices[0].get("message", {}).get("content")
            if not content:
                raise LLMError("OpenRouter returned empty content")

            result = json.loads(_strip_fenced_json(content))
            logger.info("LLM Provider=%s Model=%s completed successfully", self.provider_name, model_name)
            return result

        except httpx.TimeoutException:
            raise LLMError("OpenRouter timeout")
        except json.JSONDecodeError as e:
            raise LLMError(f"OpenRouter returned invalid JSON: {e}")
        except RateLimitError:
            raise
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"OpenRouter error: {e}")


# ============================================================
# NVIDIA
# ============================================================
class NvidiaProvider(BaseProvider):
    provider_name = "nvidia"

    def __init__(self):
        if not settings.NVIDIA_API_KEY:
            raise ConfigurationError("NVIDIA_API_KEY is missing")

    async def generate_json(self, model_name: str, prompt: str, schema: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert technical recruiter and resume evaluator. "
                        "Return only valid JSON. Do not return markdown or explanations. "
                        "Follow the requested schema exactly."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        timeout = httpx.Timeout(connect=10.0, read=settings.LLM_TIMEOUT_SECONDS, write=10.0, pool=10.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )

            if response.status_code == 429:
                raise RateLimitError("NVIDIA rate limit")
            if response.status_code == 400:
                # 400 = bad request / schema error — not a transient failure, do not retry
                raise LLMError(f"NVIDIA HTTP 400 (non-retryable): {response.text[:500]}")
            if response.status_code >= 500:
                raise LLMError(f"NVIDIA HTTP {response.status_code} (transient): {response.text[:200]}")
            if response.status_code >= 400:
                raise LLMError(f"NVIDIA HTTP {response.status_code}: {response.text[:500]}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMError("NVIDIA returned no choices")

            content = choices[0].get("message", {}).get("content")
            if not content:
                raise LLMError("NVIDIA returned empty content")

            result = json.loads(_strip_fenced_json(content))
            logger.info("LLM Provider=%s Model=%s completed successfully", self.provider_name, model_name)
            return result

        except httpx.TimeoutException:
            raise LLMError("NVIDIA timeout")
        except json.JSONDecodeError as e:
            raise LLMError(f"NVIDIA returned invalid JSON: {e}")
        except RateLimitError:
            raise
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"NVIDIA error: {e}")


# ============================================================
# ROUTER FACTORY
# ============================================================
class LLMProviderFactory:

    _providers = {}

    @classmethod
    def get_provider(cls, provider_name: str) -> BaseProvider:
        if provider_name in cls._providers:
            return cls._providers[provider_name]

        if provider_name == "groq":
            provider = GroqProvider()
        elif provider_name == "gemini":
            provider = GeminiProvider()
        elif provider_name == "openrouter":
            provider = OpenRouterProvider()
        elif provider_name == "nvidia":
            provider = NvidiaProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {provider_name}")
            
        cls._providers[provider_name] = provider
        return provider

    @staticmethod
    async def generate_with_fallback(prompt: str, schema: dict) -> dict:
        eligible_models = model_registry.get_eligible_llm_models()
        
        if not eligible_models:
            logger.error("No eligible LLM models available (all might be on cooldown).")
            raise LLMExhaustionError(
                "No eligible LLM providers available (all may be on cooldown)."
            )

        for config in eligible_models:
            # Check capability (e.g. structured output)
            if "json" not in config.capabilities:
                logger.debug(f"Skipping {config.provider}/{config.model_name}: lacks 'json' capability")
                continue

            try:
                provider = LLMProviderFactory.get_provider(config.provider)
                logger.info(f"Trying LLM provider: {config.provider}, model: {config.model_name}")
                
                result = await provider.generate_json(config.model_name, prompt, schema)
                if result:
                    return result

                logger.warning(f"LLM {config.provider}/{config.model_name} returned empty result")

            except ConfigurationError as e:
                logger.error(f"Configuration error for {config.provider}: {e}")
                continue
                
            except RateLimitError as e:
                logger.warning(f"RateLimit hit for {config.provider}/{config.model_name}: {e}. Marking cooldown.")
                model_registry.mark_llm_cooldown(config.model_name)
                # Fail over to next eligible model
                continue
                
            except LLMError as e:
                err_str = str(e)
                if "timeout" in err_str.lower() or "transient" in err_str.lower() or "50" in err_str:
                    # Timeout or 5xx server errors warrant a cooldown
                    logger.warning(f"Transient error for {config.provider}/{config.model_name}: {e}. Marking cooldown.")
                    model_registry.mark_llm_cooldown(config.model_name)
                elif "non-retryable" in err_str.lower() or "400" in err_str:
                    # Schema / config error — log at error level, skip model, no cooldown
                    logger.error(f"Non-retryable error for {config.provider}/{config.model_name}: {e}.")
                else:
                    logger.warning(f"LLM Error for {config.provider}/{config.model_name}: {e}.")
                continue

            except Exception as e:
                logger.warning(f"Provider {config.provider} failed: {e}. Moving to next provider...")
                continue

        logger.error("All configured LLM providers exhausted without a successful response.")
        raise LLMExhaustionError(
            "All configured LLM providers failed to return a valid response."
        )