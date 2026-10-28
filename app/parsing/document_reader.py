"""
Turns an uploaded resume file (PDF / DOCX / TXT) into raw text.
This is the "known risk area" flagged in the original roadmap (Phase 4) — pulled
forward here because a real backend can't demo on plain text alone.

Every function has a fallback: if a PDF is scanned/image-based and has no
extractable text layer, we raise a clear error rather than silently returning "".
"""
from pathlib import Path
from pypdf import PdfReader
import docx


class UnsupportedFileType(Exception):
    pass


class EmptyDocumentError(Exception):
    """Raised when a file parses without error but yields no usable text
    (e.g. a scanned/image-only PDF with no OCR text layer)."""
    pass


def read_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise EmptyDocumentError(
            f"No extractable text in {file_path} — likely a scanned/image PDF. "
            "OCR support (pytesseract) is a Phase 4 stretch goal, not wired in yet."
        )
    return text


def read_docx(file_path: str) -> str:
    document = docx.Document(file_path)
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs).strip()
    if not text:
        raise EmptyDocumentError(f"No extractable text in {file_path}")
    return text


def read_txt(file_path: str) -> str:
    text = Path(file_path).read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        raise EmptyDocumentError(f"No extractable text in {file_path}")
    return text


def read_resume_file(file_path: str) -> str:
    """Single entry point — dispatches on file extension."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return read_pdf(file_path)
    elif ext in (".docx", ".doc"):
        if ext == ".doc":
            raise UnsupportedFileType(
                "Legacy .doc (not .docx) isn't supported by python-docx. "
                "Ask the candidate to re-save as .docx or .pdf, or paste the text."
            )
        return read_docx(file_path)
    elif ext == ".txt":
        return read_txt(file_path)
    else:
        raise UnsupportedFileType(
            f"Unsupported file type '{ext}'. Supported: .pdf, .docx, .txt"
        )
