"""Tests for parallel execution edge cases."""

import pytest
import asyncio

from multi_agent.tools import ToolExecutor
from multi_agent.tools.builtin import register_builtin_tools


class TestParallelExecution:
    """Test suite for parallel execution edge cases."""

    @pytest.fixture
    def executor(self):
        """Create a ToolExecutor with builtin tools."""
        builtin_registry = register_builtin_tools()
        return ToolExecutor(manager=None, builtin_registry=builtin_registry)

    @pytest.mark.asyncio
    async def test_parallel_execution_speedup(self, executor):
        """Test that parallel execution is faster than serial."""
        import time
        
        tool_calls = [
            {
                "id": f"call_{i}",
                "function": {
                    "name": "system_get_time",
                    "arguments": '{}'
                }
            }
            for i in range(5)
        ]
        
        start = time.time()
        results = await executor.execute_batch(tool_calls)
        parallel_time = time.time() - start
        
        assert len(results) == 5
        # Parallel execution should be much faster than serial
        # (serial would be ~5 * time_for_one_call)
        assert parallel_time < 1.0  # Should complete in under 1 second

    @pytest.mark.asyncio
    async def test_partial_failure_handling(self, executor):
        """Test parallel execution with some tools failing."""
        tool_calls = [
            {
                "id": "call_1",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "1 + 1"}'
                }
            },
            {
                "id": "call_2",
                "function": {
                    "name": "invalid_syntax_tool",
                    "arguments": '{}'
                }
            },
            {
                "id": "call_3",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "2 + 2"}'
                }
            }
        ]
        
        results = await executor.execute_batch(tool_calls)
        assert len(results) == 3
        # First should succeed
        assert results[0]["tool_call_id"] == "call_1"
        assert "2" in results[0]["content"][0]["text"]
        # Second should fail
        assert results[1]["tool_call_id"] == "call_2"
        assert "not found" in results[1]["content"][0]["text"].lower()
        # Third should succeed
        assert results[2]["tool_call_id"] == "call_3"
        assert "4" in results[2]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_result_ordering_preserved(self, executor):
        """Test that result order matches input order regardless of completion time."""
        # Create tasks with different potential completion times
        tool_calls = [
            {
                "id": "call_1",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "sum(range(1000))"}'
                }
            },
            {
                "id": "call_2",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "1"}'
                }
            },
            {
                "id": "call_3",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "sum(range(10000))"}'
                }
            }
        ]
        
        results = await executor.execute_batch(tool_calls)
        assert len(results) == 3
        # Check order is preserved
        for i, result in enumerate(results, 1):
            assert result["tool_call_id"] == f"call_{i}"

    @pytest.mark.asyncio
    async def test_exception_handling_in_parallel(self, executor):
        """Test that exceptions in parallel execution don't crash the batch."""
        tool_calls = [
            {
                "id": "call_1",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "1 + 1"}'
                }
            },
            {
                "id": "call_2",
                "function": {
                    "name": "calculate",
                    "arguments": 'invalid json'
                }
            }
        ]
        
        # Should not raise exception
        results = await executor.execute_batch(tool_calls)
        assert len(results) == 2
        # First should succeed
        assert "2" in results[0]["content"][0]["text"]
        # Second should handle error gracefully
        assert results[1]["content"][0]["text"] is not None

    @pytest.mark.asyncio
    async def test_empty_batch(self, executor):
        """Test execute_batch() with empty list."""
        results = await executor.execute_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_single_item_batch(self, executor):
        """Test execute_batch() with single item."""
        tool_calls = [
            {
                "id": "call_1",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "42"}'
                }
            }
        ]
        results = await executor.execute_batch(tool_calls)
        assert len(results) == 1
        assert "42" in results[0]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_concurrent_batches(self, executor):
        """Test running multiple batches concurrently."""
        batch1 = [
            {
                "id": f"batch1_call_{i}",
                "function": {
                    "name": "calculate",
                    "arguments": f'{{"expression": "{i} + {i}"}}'
                }
            }
            for i in range(3)
        ]
        
        batch2 = [
            {
                "id": f"batch2_call_{i}",
                "function": {
                    "name": "calculate",
                    "arguments": f'{{"expression": "{i} * {i}"}}'
                }
            }
            for i in range(3)
        ]
        
        # Run batches concurrently
        results = await asyncio.gather(
            executor.execute_batch(batch1),
            executor.execute_batch(batch2)
        )
        
        assert len(results) == 2
        assert len(results[0]) == 3
        assert len(results[1]) == 3

    @pytest.mark.asyncio
    async def test_large_batch_execution(self, executor):
        """Test execute_batch() with many tools."""
        tool_calls = [
            {
                "id": f"call_{i}",
                "function": {
                    "name": "calculate",
                    "arguments": f'{{"expression": "{i} * 2"}}'
                }
            }
            for i in range(20)
        ]
        
        results = await executor.execute_batch(tool_calls)
        assert len(results) == 20
        # Verify all have tool_call_id
        for i, result in enumerate(results):
            assert result["tool_call_id"] == f"call_{i}"
