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
