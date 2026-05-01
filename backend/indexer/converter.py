"""Convert PPTX/PDF files to per-page PNG images for Claude Vision extraction."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path

from config import get_settings

SOFFICE = (
    os.getenv("SOFFICE_PATH")
    or shutil.which("soffice")
    or "/Applications/LibreOffice.app/Contents/MacOS/soffice"
)
RENDER_DPI = os.getenv("CONVERTER_DPI", "150")  # 150 DPI → ~2000×1125 for 16:9 slides (1.56× retina, sharp)


def _get_pdftoppm_path() -> str:
    """Get pdftoppm path from settings, env, PATH, or Mac default."""
    settings = get_settings()
    if settings.pdftoppm_path:
        return settings.pdftoppm_path
    return (
        os.getenv("PDFTOPPM_PATH")
        or shutil.which("pdftoppm")
        or "/opt/homebrew/bin/pdftoppm"
    )


def _get_pdfinfo_path() -> str:
    """Get pdfinfo path from env, PATH, or default."""
    return (
        os.getenv("PDFINFO_PATH")
        or shutil.which("pdfinfo")
        or "/usr/bin/pdfinfo"
    )


async def get_pdf_page_count(pdf_path: str | Path) -> int:
    """Return the number of pages in a PDF using PyMuPDF."""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        count = len(doc)
        doc.close()
        return count
    except Exception as e:
        import logging
        logging.warning(f"Failed to get PDF page count: {e}")
    return 0


async def get_pdf_page_count_from_bytes(data: bytes) -> int:
    """Return the number of pages in a PDF byte-stream using a temporary file."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    
    try:
        return await get_pdf_page_count(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def get_pptx_slide_count_from_bytes(data: bytes) -> int:
    """Return the number of slides in a PPTX byte-stream using python-pptx."""
    try:
        import io
        from pptx import Presentation
        prs = Presentation(io.BytesIO(data))
        return len(prs.slides)
    except Exception:
        return 0


async def get_file_page_count_from_bytes(data: bytes, filename: str) -> int:
    """Return page/slide count for a PDF, PPT, or PPTX byte-stream."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".ppt", ".pptx"):
        return await asyncio.to_thread(get_pptx_slide_count_from_bytes, data)
    return await get_pdf_page_count_from_bytes(data)


async def convert_to_page_images(
    file_path: str,
    presentation_id: str,
    presentations_root: Path | None = None,
) -> dict:
    """
    Convert a PPTX or PDF to per-page PNG images.

    Returns:
        {
            "presentation_id": str,
            "total_pages": int,
            "page_images": ["path/to/page_1.png", ...]
        }
    """
    from services.storage import presentations_root as _default_root

    root = presentations_root or _default_root()
    source = Path(file_path)
    out_dir = root / presentation_id / "pages"
    out_dir.mkdir(parents=True, exist_ok=True)

    if source.suffix.lower() in (".pptx", ".ppt"):
        pdf_path = await _pptx_to_pdf(source, out_dir)
    else:
        pdf_path = source

    page_images = await _pdf_to_pngs(pdf_path, out_dir)

    return {
        "presentation_id": presentation_id,
        "total_pages": len(page_images),
        "page_images": page_images,
    }


async def _pptx_to_pdf(pptx_path: Path, out_dir: Path) -> Path:
    """Convert PPTX to PDF using LibreOffice headless."""
    await asyncio.to_thread(
        subprocess.run,
        [SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx_path)],
        check=True,
        capture_output=True,
    )
    return out_dir / (pptx_path.stem + ".pdf")


async def _pdf_to_pngs(pdf_path: Path, out_dir: Path) -> list[str]:
    """Convert PDF pages to PNG images using PyMuPDF."""
    import fitz
    
    def _convert():
        doc = fitz.open(str(pdf_path))
        dpi = int(RENDER_DPI)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        renamed = []
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=mat, alpha=False)
            new_path = out_dir / f"page_{i}.png"
            pix.save(str(new_path))
            renamed.append(str(new_path))
        doc.close()
        return renamed
        
    return await asyncio.to_thread(_convert)
