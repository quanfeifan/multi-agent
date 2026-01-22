"""Unit tests for SSEEventAggregator.

Tests for SSE event parsing, aggregation, timeout handling, and end-of-stream detection.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from multi_agent.tools.mcp_streamable_http import (
    SSEEvent,
    SSEEventAggregator,
)


class TestSSEEvent:
    """Tests for SSEEvent dataclass parsing."""

    def test_parse_event_with_type(self):
        """Test parsing SSE event with explicit event type."""
        raw_line = "event: message\ndata: {\"text\": \"hello\"}\n"
        event = SSEEvent.parse(raw_line)

        assert event.event_type == "message"
        assert event.data == {"text": "hello"}
        assert isinstance(event.timestamp, datetime)

    def test_parse_data_only(self):
        """Test parsing SSE line with only data field."""
        raw_line = "data: {\"content\": \"test\"}\n"
        event = SSEEvent.parse(raw_line)

        assert event.event_type == "message"  # Default
        assert event.data == {"content": "test"}

    def test_parse_end_event(self):
        """Test parsing end-of-stream event."""
        raw_line = "event: end\ndata: {}\n"
        event = SSEEvent.parse(raw_line)

        assert event.event_type == "end"
        assert event.data == {}

    def test_parse_error_event(self):
        """Test parsing error event."""
        raw_line = "event: error\ndata: {\"message\": \"Stream failed\"}\n"
        event = SSEEvent.parse(raw_line)

        assert event.event_type == "error"
        assert event.data == {"message": "Stream failed"}

    def test_parse_invalid_json(self):
        """Test parsing event with invalid JSON data."""
        raw_line = "data: not-valid-json\n"
        event = SSEEvent.parse(raw_line)

        assert event.data == {"raw": "not-valid-json"}

    def test_parse_empty_data(self):
        """Test parsing event with empty data."""
        raw_line = "event: message\ndata: \n"
        event = SSEEvent.parse(raw_line)

        assert event.event_type == "message"
        assert event.data == {}


class TestSSEEventAggregator:
    """Tests for SSEEventAggregator."""

    @pytest.fixture
    def aggregator(self):
        """Create SSEEventAggregator instance."""
        return SSEEventAggregator(stream_timeout=120)

    @pytest.fixture
    def mock_response(self):
        """Create mock aiohttp response."""
        response = AsyncMock()
        response.headers = {}
        response.content = AsyncMock()
        return response

    def test_init(self):
        """Test aggregator initialization."""
        aggregator = SSEEventAggregator(stream_timeout=60)
        assert aggregator.stream_timeout == 60

    @pytest.mark.asyncio
    async def test_aggregate_simple_message(self, aggregator, mock_response):
        """Test aggregating a single message event."""
        lines = [
            b'event: message\ndata: {"result": {"content": [{"text": "hello"}]}}\n\n',
            b'event: end\ndata: {}\n\n',
        ]

        # Create proper async iterator
        async def mock_lines():
            for line in lines:
                yield line

        mock_response.content = mock_lines()

        result = await aggregator.aggregate_sse_stream(mock_response)

        assert "result" in result
        assert result["result"]["content"][0]["text"] == "hello"

    @pytest.mark.asyncio
    async def test_aggregate_multiple_messages(self, aggregator, mock_response):
        """Test aggregating multiple message events into one result."""
        lines = [
            b'event: message\ndata: {"result": {"content": [{"type": "text", "text": "Hello"}]}}\n\n',
            b'event: message\ndata: {"result": {"content": [{"type": "text", "text": " World"}]}}\n\n',
            b'event: message\ndata: {"result": {"content": [{"type": "text", "text": "!"}]}}\n\n',
            b'event: end\ndata: {}\n\n',
        ]

        async def mock_lines():
            for line in lines:
                yield line

        mock_response.content = mock_lines()

        result = await aggregator.aggregate_sse_stream(mock_response)

        # All content should be merged
        content_list = result["result"]["content"]
        assert len(content_list) == 3
        assert content_list[0]["text"] == "Hello"
        assert content_list[1]["text"] == " World"
        assert content_list[2]["text"] == "!"

    @pytest.mark.asyncio
    async def test_aggregate_respects_end_marker(self, aggregator, mock_response):
        """Test that aggregation stops at end event marker."""
        lines = [
            b'event: message\ndata: {"result": {"content": [{"text": "before"}]}}\n\n',
            b'event: end\ndata: {}\n\n',
            b'event: message\ndata: {"result": {"content": [{"text": "after"}]}}\n\n',  # Should be ignored
        ]

        async def mock_lines():
            for line in lines:
                yield line

        mock_response.content = mock_lines()

        result = await aggregator.aggregate_sse_stream(mock_response)

        # Should only include first message
        assert len(result["result"]["content"]) == 1
        assert result["result"]["content"][0]["text"] == "before"

    @pytest.mark.asyncio
    async def test_aggregate_timeout(self, aggregator, mock_response):
        """Test timeout during aggregation."""
        async def mock_slow_lines():
            # First line arrives quickly
            yield b'event: message\ndata: {"result": {"content": [{"text": "start"}]}}\n\n'
            # Second line takes too long
            await asyncio.sleep(2)
            yield b'event: end\ndata: {}\n\n'

        mock_response.content = mock_slow_lines()

        # Use short timeout for testing
        aggregator.stream_timeout = 1

        with pytest.raises(TimeoutError) as exc_info:
            await aggregator.aggregate_sse_stream(mock_response)

        assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_aggregate_error_event(self, aggregator, mock_response):
        """Test that error events raise RuntimeError."""
        lines = [
            b'event: message\ndata: {"result": {"content": [{"text": "start"}]}}\n\n',
            b'event: error\ndata: {"message": "Stream error occurred"}\n\n',
        ]

        async def mock_lines():
            for line in lines:
                yield line

        mock_response.content = mock_lines()

        with pytest.raises(RuntimeError) as exc_info:
            await aggregator.aggregate_sse_stream(mock_response)

        assert "Stream error occurred" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_aggregate_empty_stream(self, aggregator, mock_response):
        """Test aggregating empty stream."""
        async def mock_empty_lines():
            return
            yield  # Make it a generator

        mock_response.content = mock_empty_lines()

        result = await aggregator.aggregate_sse_stream(mock_response)

        assert result == {}

    @pytest.mark.asyncio
    async def test_aggregate_skips_empty_lines(self, aggregator, mock_response):
        """Test that empty lines are skipped."""
        lines = [
            b'\n\n',  # Empty line
            b'event: message\ndata: {"result": {"content": [{"text": "hello"}]}}\n\n',
            b'   \n',  # Whitespace only
            b'event: end\ndata: {}\n\n',
        ]

        async def mock_lines():
            for line in lines:
                yield line

        mock_response.content = mock_lines()

        result = await aggregator.aggregate_sse_stream(mock_response)

        assert result["result"]["content"][0]["text"] == "hello"

    @pytest.mark.asyncio
    async def test_aggregate_non_message_events(self, aggregator, mock_response):
        """Test handling non-message events (keep-alive, etc)."""
        lines = [
            b': keep-alive\n\n',  # SSE comment/keep-alive
            b'event: message\ndata: {"result": {"content": [{"text": "hello"}]}}\n\n',
            b'event: end\ndata: {}\n\n',
        ]

        async def mock_lines():
            for line in lines:
                yield line

        mock_response.content = mock_lines()

        result = await aggregator.aggregate_sse_stream(mock_response)

        # Should still work
        assert result["result"]["content"][0]["text"] == "hello"


class TestSSEEventAggregatorHelpers:
    """Tests for SSEEventAggregator helper methods."""

    @pytest.fixture
    def aggregator(self):
        """Create SSEEventAggregator instance."""
        return SSEEventAggregator(stream_timeout=120)

    def test_parse_sse_line_message(self, aggregator):
        """Test parsing SSE message line."""
        line = "event: message\ndata: {\"text\": \"hello\"}\n"
        event_type, data = aggregator._parse_sse_line(line)

        assert event_type == "message"
        assert data == {"text": "hello"}

    def test_parse_sse_line_data_only(self, aggregator):
        """Test parsing SSE line with only data."""
        line = "data: {\"content\": \"test\"}\n"
        event_type, data = aggregator._parse_sse_line(line)

        assert event_type == "message"  # Default
        assert data == {"content": "test"}

    def test_detect_end_of_stream_with_end_event(self, aggregator):
        """Test end detection with end event."""
        events = [
            SSEEvent(event_type="message", data={"text": "hello"}, raw_data="", timestamp=datetime.now()),
            SSEEvent(event_type="end", data={}, raw_data="", timestamp=datetime.now()),
        ]

        assert aggregator._detect_end_of_stream(events) is True

    def test_detect_end_of_stream_with_done_flag(self, aggregator):
        """Test end detection with done flag in data."""
        events = [
            SSEEvent(
                event_type="message",
                data={"done": True},
                raw_data="",
                timestamp=datetime.now()
            ),
        ]

        assert aggregator._detect_end_of_stream(events) is True

    def test_detect_end_of_stream_not_complete(self, aggregator):
        """Test end detection when stream is not complete."""
        events = [
            SSEEvent(
                event_type="message",
                data={"text": "still going"},
                raw_data="",
                timestamp=datetime.now()
            ),
        ]

        assert aggregator._detect_end_of_stream(events) is False

    def test_detect_end_of_stream_empty_events(self, aggregator):
        """Test end detection with empty event list."""
        assert aggregator._detect_end_of_stream([]) is False

    def test_merge_events_single(self, aggregator):
        """Test merging single event."""
        events = [
            SSEEvent(
                event_type="message",
                data={"result": {"content": [{"text": "hello"}]}},
                raw_data="",
                timestamp=datetime.now()
            ),
        ]

        result = aggregator._merge_events(events)

        assert result == {"result": {"content": [{"text": "hello"}]}}

    def test_merge_events_multiple(self, aggregator):
        """Test merging multiple events."""
        events = [
            SSEEvent(
                event_type="message",
                data={"result": {"content": [{"text": "hello"}]}},
                raw_data="",
                timestamp=datetime.now()
            ),
            SSEEvent(
                event_type="message",
                data={"result": {"content": [{"text": " world"}]}},
                raw_data="",
                timestamp=datetime.now()
            ),
            SSEEvent(
                event_type="message",
                data={"result": {"content": [{"text": "!"}]}},
                raw_data="",
                timestamp=datetime.now()
            ),
        ]

        result = aggregator._merge_events(events)

        content = result["result"]["content"]
        assert len(content) == 3
        assert content[0]["text"] == "hello"
        assert content[1]["text"] == " world"
        assert content[2]["text"] == "!"

    def test_merge_events_empty(self, aggregator):
        """Test merging empty event list."""
        result = aggregator._merge_events([])
        assert result == {}

    def test_merge_events_non_message_filtered(self, aggregator):
        """Test that non-message events are filtered during merge."""
        events = [
            SSEEvent(
                event_type="message",
                data={"result": {"content": [{"text": "hello"}]}},
                raw_data="",
                timestamp=datetime.now()
            ),
            SSEEvent(
                event_type="keep-alive",
                data={},
                raw_data="",
                timestamp=datetime.now()
            ),
        ]

        result = aggregator._merge_events(events)

        # Should only have message event data
        assert result == {"result": {"content": [{"text": "hello"}]}}
