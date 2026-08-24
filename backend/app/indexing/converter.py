from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path

from app.config import get_settings
from app.storage import presentation_dir


RENDER_DPI = int(os.environ.get("CONVERTER_DPI", "150"))


def _find_soffice() -> str | None:
    settings = get_settings()
    if settings.soffice_path and Path(settings.soffice_path).exists():
        return settings.soffice_path
    found = shutil.which("soffice") or shutil.which("soffice.exe")
    if found:
        return found
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/bin/soffice",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


async def convert_to_page_images(file_path: Path, presentation_id: str) -> list[Path]:
    return await asyncio.to_thread(_convert_sync, file_path, presentation_id)


def _convert_sync(file_path: Path, presentation_id: str) -> list[Path]:
    out_dir = presentation_dir(presentation_id) / "pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = file_path
    suffix = file_path.suffix.lower()
    if suffix in {".pptx", ".ppt"}:
        pdf_path = _pptx_to_pdf(file_path, out_dir.parent)
    return _pdf_to_pngs(pdf_path, out_dir)


def _pptx_to_pdf(pptx_path: Path, out_dir: Path) -> Path:
    soffice = _find_soffice()
    if not soffice:
        raise RuntimeError("LibreOffice (soffice) not found — required for PPTX conversion")
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx_path)],
        check=True,
        capture_output=True,
    )
    pdf = out_dir / f"{pptx_path.stem}.pdf"
    if not pdf.exists():
        raise RuntimeError(f"LibreOffice did not produce PDF for {pptx_path.name}")
    return pdf


def _pdf_to_pngs(pdf_path: Path, out_dir: Path) -> list[Path]:
    import fitz

    zoom = RENDER_DPI / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    doc = fitz.open(pdf_path)
    paths: list[Path] = []
    try:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            dest = out_dir / f"page_{i}.png"
            pix.save(str(dest))
            paths.append(dest)
    finally:
        doc.close()
    return paths
