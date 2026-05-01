from typing import Optional

from pydantic import BaseModel


class PresentationSummary(BaseModel):
    presentation_id: str
    filename: str
    status: str
    total_pages: Optional[int] = None
    indexed_pages: int = 0
    document_id: Optional[str] = None
    azure_indexed_chunks: Optional[int] = None
    metadata_provider: Optional[str] = None
    metadata_model: Optional[str] = None
    index_error: Optional[str] = None
