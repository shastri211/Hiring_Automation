import pytest
from app.services.extractor.factory import get_extractor
from app.services.extractor.pdf_extractor import PDFExtractor
from app.services.extractor.docx_extractor import DOCXExtractor

def test_get_extractor():
    pdf_ext = get_extractor("test.pdf")
    assert isinstance(pdf_ext, PDFExtractor)
    
    docx_ext = get_extractor("test.docx")
    assert isinstance(docx_ext, DOCXExtractor)

    with pytest.raises(ValueError):
        get_extractor("test.txt")


def test_pdf_extractor_builds_without_gemini_key():
    """A text-only PDF never needs OCR, so constructing the extractor must
    not require GEMINI_API_KEY (genai.Client raises without one)."""
    from unittest.mock import patch
    with patch("app.services.extractor.gemini_ocr.settings.GEMINI_API_KEY", None):
        assert isinstance(PDFExtractor(), PDFExtractor)


@pytest.mark.asyncio
async def test_ocr_skipped_without_gemini_key():
    from unittest.mock import patch
    from app.services.extractor.gemini_ocr import GeminiOCREngine
    with patch("app.services.extractor.gemini_ocr.settings.GEMINI_API_KEY", None), \
         patch("app.services.extractor.gemini_ocr.genai.Client") as mock_client:
        assert await GeminiOCREngine().extract_text_from_image("page.png") == ""
        mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_ocr_returns_model_text(tmp_path):
    from unittest.mock import patch, MagicMock
    from PIL import Image
    from app.services.extractor.gemini_ocr import GeminiOCREngine
    image_path = tmp_path / "page.png"
    Image.new("RGB", (10, 10)).save(image_path)
    with patch("app.services.extractor.gemini_ocr.genai.Client") as mock_client:
        mock_client.return_value.models.generate_content.return_value = MagicMock(text="Jane Doe\nPython")
        assert await GeminiOCREngine().extract_text_from_image(str(image_path)) == "Jane Doe\nPython"
