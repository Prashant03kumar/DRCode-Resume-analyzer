import io
import pypdf
import docx
from config import logger

async def extract_text_from_file(file, file_name: str) -> str:
    """Extracts text seamlessly from PDF, DOCX, or TXT formats."""
    file_bytes = await file.download_as_bytearray()
    text = ""
    file_ext = file_name.split(".")[-1].lower()
    
    try:
        if file_ext == "pdf":
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        elif file_ext in ["docx", "doc"]:
            doc = docx.Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif file_ext == "txt":
            text = file_bytes.decode("utf-8")
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")
    except Exception as e:
        logger.error(f"Error parsing {file_name}: {e}")
        return None
        
    return text.strip()
