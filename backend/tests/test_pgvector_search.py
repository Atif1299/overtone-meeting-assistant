from __future__ import annotations

import asyncio

from config import Settings
from services.azure_search import AzureSearchClient, _parse_content_type


def test_parse_odata_content_type_filter():
    assert _parse_content_type("content_type eq 'content'") == "content"
    assert _parse_content_type("content_type eq 'brief'") == "brief"
    assert _parse_content_type(None) is None


def test_search_client_disabled_without_postgres():
    client = AzureSearchClient(Settings(database_url=""))
    assert client.enabled is False
    assert asyncio.run(client.filtered_search(query="pricing", document_id="x")) == []
