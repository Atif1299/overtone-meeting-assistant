from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Must be importable without side effects
from indexer.converter import (
    _pdf_to_pngs,
    _pptx_to_pdf,
    convert_to_page_images,
)


def test_convert_pdf_returns_correct_structure(tmp_path):
    """convert_to_page_images returns dict with presentation_id, total_pages, page_images."""
    fake_pdf = tmp_path / "slide.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    fake_pages = [
        str(tmp_path / "pages" / "page_1.png"),
        str(tmp_path / "pages" / "page_2.png"),
    ]

    with patch("indexer.converter._pdf_to_pngs", new=AsyncMock(return_value=fake_pages)):
        result = asyncio.run(
            convert_to_page_images(str(fake_pdf), "pres-001", presentations_root=tmp_path)
        )

    assert result["presentation_id"] == "pres-001"
    assert result["total_pages"] == 2
    assert result["page_images"] == fake_pages


def test_convert_pptx_calls_libreoffice_first(tmp_path):
    """PPTX input triggers LibreOffice conversion before PDF→PNG."""
    fake_pptx = tmp_path / "deck.pptx"
    fake_pptx.write_bytes(b"PK fake pptx bytes")

    fake_pdf = tmp_path / "pages" / "deck.pdf"
    fake_pages = [str(tmp_path / "pages" / "page_1.png")]

    with (
        patch("indexer.converter._pptx_to_pdf", new=AsyncMock(return_value=fake_pdf)) as mock_lo,
        patch("indexer.converter._pdf_to_pngs", new=AsyncMock(return_value=fake_pages)),
    ):
        asyncio.run(convert_to_page_images(str(fake_pptx), "pres-002", presentations_root=tmp_path))

    mock_lo.assert_awaited_once()


def test_pdf_to_pngs_renames_to_page_n(tmp_path):
    """_pdf_to_pngs renames pdftoppm output (page-01.png) to page_1.png."""
    out_dir = tmp_path / "pages"
    out_dir.mkdir()

    # Simulate pdftoppm output files
    (out_dir / "page-01.png").write_bytes(b"png1")
    (out_dir / "page-02.png").write_bytes(b"png2")

    def fake_run(cmd, **kwargs):
        pass  # pdftoppm already "ran" above — files exist

    with patch("indexer.converter.subprocess.run", side_effect=fake_run):
        result = asyncio.run(_pdf_to_pngs(tmp_path / "slide.pdf", out_dir))

    assert len(result) == 2
    assert Path(result[0]).name == "page_1.png"
    assert Path(result[1]).name == "page_2.png"
    assert Path(result[0]).exists()
