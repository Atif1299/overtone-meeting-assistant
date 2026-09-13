from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.realtime.relay import RelayRuntime


@pytest.mark.asyncio
async def test_gemini_tools_skip_send_when_interrupted():
    runtime = RelayRuntime(MagicMock(), "sid-cancel", "gemini")
    runtime._gemini_session = SimpleNamespace(send_tool_response=AsyncMock())
    runtime._generation = 2
    tool_call = SimpleNamespace(function_calls=[])

    await runtime._handle_gemini_tools(tool_call, generation=1)

    runtime._gemini_session.send_tool_response.assert_not_awaited()
