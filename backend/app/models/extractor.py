"""Text extraction utilities."""
from typing import List
import PyPDF2

async def extract_text_from_pdf(file_path: str) -> str:
    """Extract text content from a PDF file.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content
    """
    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text