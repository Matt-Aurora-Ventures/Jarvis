from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.extracted.kr8tiv_memory.conversation_export import (
    ConversationExportFormat,
    ConversationExporter,
    ExportOptions,
)


@pytest.fixture
def exporter(tmp_path):
    exp = ConversationExporter(output_dir=str(tmp_path), instance_id="kr8tiv")
    return exp


@pytest.mark.asyncio
async def test_export_markdown_to_string(exporter):
    exporter.get_memories_fn = _async_value(
        [
            {
                "content": "Kr8tiv prioritizes creator-friendly UX.",
                "tags": ["product", "ux"],
                "created_at": datetime.now().isoformat(),
            }
        ]
    )
    exporter.get_conversations_fn = _async_value(
        [
            {
                "role": "user",
                "content": "What is the launch sequence?",
                "timestamp": datetime.now().isoformat(),
            }
        ]
    )

    result = await exporter.export_to_string(
        ExportOptions(format=ConversationExportFormat.MARKDOWN)
    )

    assert result.success is True
    assert result.content is not None
    assert "# KR8TIV Memory Export" in result.content
    assert "Kr8tiv prioritizes creator-friendly UX." in result.content


@pytest.mark.asyncio
async def test_export_json_with_date_filter(exporter):
    old = (datetime.now() - timedelta(days=20)).isoformat()
    new = datetime.now().isoformat()

    exporter.get_memories_fn = _async_value(
        [
            {"content": "Old", "tags": ["t"], "created_at": old},
            {"content": "New", "tags": ["t"], "created_at": new},
        ]
    )
    exporter.get_conversations_fn = _async_value([])

    result = await exporter.export(
        ExportOptions(
            format=ConversationExportFormat.JSON,
            start_date=datetime.now() - timedelta(days=3),
        )
    )

    assert result.success is True
    assert result.memories_exported == 1


def _async_value(value):
    async def _inner():
        return value

    return _inner

