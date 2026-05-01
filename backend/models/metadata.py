from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class PageMetadata(BaseModel):
    page_number: int
    title: Optional[str] = None
    description: Optional[str] = ""
    tag: Optional[str] = None
    section_label: Optional[str] = None
    speaker_notes: Optional[str] = ""
    layout: Optional[str] = None
    content: Optional[str] = None
    content_text: Optional[str] = None
    data_points: Optional[Dict[str, Any]] = None
    visuals: Optional[List[Dict[str, Any]]] = None
    key_topics: Optional[List[str]] = None
    entities: Optional[List[str]] = None
    has_table: Optional[bool] = None
    has_chart: Optional[bool] = None
    has_diagram: Optional[bool] = None
    questions_answered: Optional[List[str]] = None

class PresentationMetadata(BaseModel):
    session_id: Optional[str] = None
    title: Optional[str] = None
    account_name: Optional[str] = None
    industry: Optional[str] = None
    date_range: Optional[str] = None
    total_pages: Optional[int] = None
    pages: List[PageMetadata]
