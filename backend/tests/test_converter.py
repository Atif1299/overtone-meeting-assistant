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


def test_soffice_path_accepts_windows_candidates(monkeypatch, tmp_path):
    fake = tmp_path / "soffice.exe"
    fake.write_bytes(b"")
    monkeypatch.setenv("SOFFICE_PATH", str(fake))
    from indexer.converter import _get_soffice_path

    assert _get_soffice_path() == str(fake)


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


def test_pdf_to_pngs_writes_page_n(tmp_path):
    """_pdf_to_pngs writes page_N.png files via PyMuPDF."""
    out_dir = tmp_path / "pages"
    out_dir.mkdir()

    class FakePix:
        def save(self, path):
            Path(path).write_bytes(b"png")

    class FakePage:
        def get_pixmap(self, matrix, alpha):
            return FakePix()

    class FakeDoc:
        def __init__(self):
            self._pages = [FakePage(), FakePage()]

        def __iter__(self):
            return iter(self._pages)

        def close(self):
            return None

    fake_fitz = MagicMock()
    fake_fitz.open.return_value = FakeDoc()
    with patch.dict("sys.modules", {"fitz": fake_fitz}):
        result = asyncio.run(_pdf_to_pngs(tmp_path / "slide.pdf", out_dir))

    assert len(result) == 2
    assert Path(result[0]).name == "page_1.png"
    assert Path(result[1]).name == "page_2.png"
    assert Path(result[0]).exists()
