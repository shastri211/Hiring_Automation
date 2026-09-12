import pymupdf as fitz
import os
from .base import BaseExtractor, BaseOCREngine
from .gemini_ocr import GeminiOCREngine

class PDFExtractor(BaseExtractor):
    def __init__(self, ocr_engine: BaseOCREngine = None):
        self.ocr_engine = ocr_engine or GeminiOCREngine()

    async def extract(self, file_path: str) -> str:
        text_content = []
        try:
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text("text").strip()
                
                if len(page_text) < 50:
                    pix = page.get_pixmap()
                    temp_img_path = f"{file_path}_page_{page_num}.png"
                    pix.save(temp_img_path)
                    try:
                        ocr_text = await self.ocr_engine.extract_text_from_image(temp_img_path)
                        text_content.append(ocr_text)
                    finally:
                        if os.path.exists(temp_img_path):
                            os.remove(temp_img_path)
                else:
                    text_content.append(page_text)
            
            return "\n\n".join(text_content).strip()
        except Exception as e:
            raise Exception(f"PDF extraction failed: {str(e)}")
