import asyncio
import os
import json
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Mock settings before importing modules
os.environ["AZURE_SEARCH_ENDPOINT"] = "https://mock.search.windows.net"
os.environ["AZURE_SEARCH_KEY"] = "mock-key"
os.environ["AZURE_SEARCH_INDEX_NAME"] = "overtone"
os.environ["OPENAI_API_KEY"] = "sk-mock"

from indexer import pipeline
from orchestrator.rag_retriever import search_presentation
from services import storage as storage_mod
from orchestrator.realtime_tools import RealtimeToolExecutor

async def verify():
    # 1. Setup mock presentation
    presentation_id = "test_rich_meta"
    
    # Register properly so _META is populated
    storage_mod.register_presentation(
        presentation_id=presentation_id,
        filename="source.pdf",
        status="pending"
    )
    
    root = Path(storage_mod.presentations_root()) / presentation_id
    # Fake source file
    source_path = root / "source.pdf"
    source_path.write_bytes(b"%PDF-1.4 mock")
    
    # Save helix.json as provided_metadata.json
    helix_content = {
        "title": "Helix Presentation",
        "account_name": "Helix Corp",
        "glossary": {"ACV": "Annual Contract Value"},
        "known_contradictions": [
            {"summary": "LinkedIn has high credit but low lift", "referenced_pages": [3, 9]}
        ],
        "pages": [
            {
                "page_number": 1,
                "title": "Slide 1",
                "content": "Description of slide 1",
                "data_points": {"KPI": "High"},
                "visuals": [{"description": "A beautiful chart"}]
            }
        ]
    }
    with open(root / "provided_metadata.json", "w") as f:
        json.dump(helix_content, f)
        
    storage_mod.update_presentation_meta(presentation_id, status="pending", filename="source.pdf")

    # 2. Mock external dependencies
    with patch("indexer.pipeline.AzureBlobStorageClient") as mock_blob:
        mock_blob.return_value.enabled = False
        with patch("indexer.pipeline._upload_to_search") as mock_upload:
            mock_upload.return_value = 1
            
            # 3. Run indexing
            print("🚀 Running index job...")
            await pipeline.run_index_job(presentation_id)
            
    # 4. Verify local index was created with rich metadata
    print("🔍 Verifying local index...")
    # Mock generating query embedding to fail fast for local fallback
    with patch("orchestrator.rag_retriever._generate_query_embedding", AsyncMock(return_value=None)):
        hits = await search_presentation("Slide 1", presentation_id)
        
    if not hits:
        print(f"❌ No hits found for presentation {presentation_id}")
        rows = storage_mod.load_chunk_rows(presentation_id)
        print(f"Local chunk_rows count: {len(rows)}")
        if rows:
            print(f"First row content: {rows[0].get('content_text')}")
            
    assert len(hits) >= 1
    hit = hits[0]
    assert "full_metadata_json" in hit
    assert '"data_points": {"KPI": "High"}' in hit["full_metadata_json"]
    print("✅ Local index contains full_metadata_json")

    # 5. Verify search_and_answer tool response
    print("🤖 Verifying search_and_answer tool...")
    mock_ws = MagicMock()
    mock_sess = MagicMock()
    mock_sess.presentation_id = presentation_id
    mock_sess.session_id = "test_sess"
    
    executor = RealtimeToolExecutor()
    # Inject current session into executor's store if needed, or mock _get_session
    with patch("orchestrator.realtime_tools._get_session", AsyncMock(return_value=mock_sess)):
         # We need to mock the search_presentation call inside the tool to return our hits
         with patch("orchestrator.realtime_tools.rag_retriever.search_presentation", AsyncMock(return_value=hits)):
             result = await executor._search_and_answer(session_id="test_sess", args={"user_question": "tell me about KPIs"})
             
             assert result["ok"] is True
             assert "rich_metadata" in result
             assert result["rich_metadata"]["page_details"]["data_points"]["KPI"] == "High"
             assert result["rich_metadata"]["presentation_context"]["account"] == "Helix Corp"
             print("✅ Tool successfully returned rich structured metadata")

    # 6. Verify get_slide_details tool
    print("🤖 Verifying get_slide_details tool...")
    with patch("orchestrator.realtime_tools._get_session", AsyncMock(return_value=mock_sess)):
        result = await executor._get_slide_details(session_id="test_sess", args={"page_number": 1})
        assert result["ok"] is True
        assert result["page_number"] == 1
        assert result["rich_metadata"]["page_details"]["data_points"]["KPI"] == "High"
        print("✅ get_slide_details returned correct page data")

    # 7. Verify compose_realtime_instructions
    print("📋 Verifying instruction composition...")
    from agents.runtime import compose_realtime_instructions
    instructions = compose_realtime_instructions(
        system_prompt="Base prompt",
        presentation_id=presentation_id
    )
    assert "TARGET ACCOUNT: Helix Corp" in instructions
    assert "GLOSSARY: ACV: Annual Contract Value" in instructions
    assert "KNOWN CONTRADICTIONS: LinkedIn has high credit but low lift" in instructions
    print("✅ Initial instructions contain global metadata")

    print("\n🎉 ALL TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(verify())
