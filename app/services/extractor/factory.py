from .pdf_extractor import PDFExtractor
from .docx_extractor import DOCXExtractor

def get_extractor(file_path: str, mime_type: str = None):
    if file_path.lower().endswith('.pdf') or mime_type == 'application/pdf':
        return PDFExtractor()
    elif file_path.lower().endswith('.docx') or mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        return DOCXExtractor()
    else:
        raise ValueError("Unsupported file format")
