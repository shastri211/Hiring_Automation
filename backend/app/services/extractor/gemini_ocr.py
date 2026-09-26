import asyncio
import logging
import google.genai as genai
from google.genai import types
from PIL import Image
from .base import BaseOCREngine
from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiOCREngine(BaseOCREngine):
    def __init__(self):
        # Created on first OCR use, not here: genai.Client raises without an
        # API key, and PDFExtractor builds this engine for every PDF - even
        # text-only ones that never need OCR.
        self._client = None

    async def extract_text_from_image(self, file_path: str) -> str:
        if not settings.GEMINI_API_KEY:
            logger.warning(f"GEMINI_API_KEY is not set - skipping OCR for {file_path}.")
            return ""

        def _call() -> str:
            if self._client is None:
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
            with Image.open(file_path) as img:
                response = self._client.models.generate_content(
                    model=settings.gemini_ocr_model,
                    contents=[
                        "Extract all the text from this resume page accurately. Keep the structure as much as possible, just output the raw text.",
                        img
                    ],
                    config=types.GenerateContentConfig(
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )
            return response.text or ""

        try:
            # The SDK call is blocking - run it off the event loop so it can't
            # stall the worker's other consumers and heartbeats.
            return await asyncio.wait_for(asyncio.to_thread(_call), timeout=settings.LLM_TIMEOUT_SECONDS)
        except Exception:
            # Swallowed intentionally (a failed OCR page degrades to empty
            # text rather than failing the whole resume) - but must still be
            # visible server-side, not silently dropped, so auth/quota/
            # network failures here are actually diagnosable.
            logger.exception(f"Gemini OCR failed for {file_path}")
            return ""
