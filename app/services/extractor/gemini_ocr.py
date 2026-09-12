import os
import google.genai as genai
from google.genai import types
from PIL import Image
from .base import BaseOCREngine
from app.core.config import settings

class GeminiOCREngine(BaseOCREngine):
    def __init__(self):
        api_key = settings.GEMINI_API_KEY or os.environ.get('GEMINI_API_KEY')
        self.client = genai.Client(api_key=api_key)

    async def extract_text_from_image(self, file_path: str) -> str:
        try:
            img = Image.open(file_path)
            response = self.client.models.generate_content(
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
        except Exception as e:
            print(f"Gemini OCR Error: {e}")
            return ""
