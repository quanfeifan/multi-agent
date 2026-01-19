"""Tests for file tools."""

import os
import tempfile
from pathlib import Path

import pytest

from multi_agent.tools.builtin.file import (
    FileReadTool,
    FileWriteTool,
    FileListTool,
    FileInfoTool,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    return tmp_path


class TestFileReadTool:
    """Test FileReadTool class."""

    @pytest.mark.asyncio
    async def test_read_file_success(self, temp_dir):
        """Test reading a file successfully."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")

        tool = FileReadTool()
        result = await tool.execute(path=str(test_file))

        assert result.success is True
        assert result.data == "Hello, World!"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, temp_dir):
        """Test reading a non-existent file."""
        tool = FileReadTool()
        result = await tool.execute(path="nonexistent.txt")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_read_file_outside_cwd(self, temp_dir):
        """Test reading file outside CWD is rejected."""
        tool = FileReadTool()
        # Try to read /etc/passwd which should be outside CWD
        result = await tool.execute(path="/etc/passwd")

        assert result.success is False
        assert "denied" in result.error.lower() or "outside" in result.error.lower()

    @pytest.mark.asyncio
    async def test_read_file_truncates_large_content(self, temp_dir):
        """Test large file is truncated to 100KB limit."""
        # Create file larger than 100KB
        large_content = "x" * (150 * 1024)
        test_file = temp_dir / "large.txt"
        test_file.write_text(large_content)

        tool = FileReadTool()
        result = await tool.execute(path=str(test_file))

        assert result.success is True
        assert result.truncated is True
        assert len(result.data.encode("utf-8")) <= 100 * 1024


class TestFileWriteTool:
    """Test FileWriteTool class."""

    @pytest.mark.asyncio
    async def test_write_file_success(self, temp_dir):
        """Test writing a file successfully."""
        test_file = temp_dir / "write_test.txt"

        tool = FileWriteTool()
        result = await tool.execute(path=str(test_file), content="test content")

        assert result.success is True
        assert test_file.read_text() == "test content"

    @pytest.mark.asyncio
    async def test_write_file_creates_parent_dirs(self, temp_dir):
        """Test writing creates parent directories."""
        tool = FileWriteTool()
        result = await tool.execute(
            path=str(temp_dir / "subdir" / "test.txt"),
            content="content"
        )

        assert result.success is True
        assert (temp_dir / "subdir" / "test.txt").exists()

    @pytest.mark.asyncio
    async def test_write_file_outside_cwd(self, temp_dir):
        """Test writing file outside CWD is rejected."""
        tool = FileWriteTool()
        result = await tool.execute(path="/etc/test_write.txt", content="test")

        assert result.success is False
        assert "denied" in result.error.lower() or "outside" in result.error.lower()

    @pytest.mark.asyncio
    async def test_write_file_missing_content(self, temp_dir):
        """Test writing with missing content parameter."""
        tool = FileWriteTool()
        result = await tool.execute(path="test.txt")

        assert result.success is False
        assert "required" in result.error.lower()


class TestFileListTool:
    """Test FileListTool class."""

    @pytest.mark.asyncio
    async def test_list_directory(self, temp_dir):
        """Test listing directory contents."""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "subdir").mkdir()

        tool = FileListTool()
        result = await tool.execute(path=str(temp_dir))

        assert result.success is True
        assert "file1.txt" in result.data
        assert "file2.txt" in result.data
        assert "subdir" in result.data

    @pytest.mark.asyncio
    async def test_list_directory_default_to_cwd(self, temp_dir):
        """Test listing with default path (current directory)."""
        tool = FileListTool()
        # Change to temp directory
        original_cwd = Path.cwd()
        try:
            os.chdir(temp_dir)
            (temp_dir / "test.txt").write_text("test")

            result = await tool.execute()
            assert result.success is True
            assert "test.txt" in result.data
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_list_nonexistent_directory(self, temp_dir):
        """Test listing non-existent directory."""
        tool = FileListTool()
        result = await tool.execute(path="nonexistent_dir")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_list_file_not_directory(self, temp_dir):
        """Test listing a file (not directory)."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        tool = FileListTool()
        result = await tool.execute(path=str(test_file))

        assert result.success is False
        assert "not a directory" in result.error.lower()

    @pytest.mark.asyncio
    async def test_list_outside_cwd(self, temp_dir):
        """Test listing outside CWD is rejected."""
        tool = FileListTool()
        result = await tool.execute(path="/etc")

        assert result.success is False
        assert "denied" in result.error.lower() or "outside" in result.error.lower()


class TestFileInfoTool:
    """Test FileInfoTool class."""

    @pytest.mark.asyncio
    async def test_get_file_info(self, temp_dir):
        """Test getting file information."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        tool = FileInfoTool()
        result = await tool.execute(path=str(test_file))

        assert result.success is True
        assert "file" in result.data.lower()
        assert "12 bytes" in result.data  # "test content" is 12 bytes
        assert "Modified:" in result.data

    @pytest.mark.asyncio
    async def test_get_directory_info(self, temp_dir):
        """Test getting directory information."""
        tool = FileInfoTool()
        result = await tool.execute(path=str(temp_dir))

        assert result.success is True
        assert "directory" in result.data.lower()

    @pytest.mark.asyncio
    async def test_get_info_nonexistent(self, temp_dir):
        """Test getting info for non-existent path."""
        tool = FileInfoTool()
        result = await tool.execute(path="nonexistent.txt")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_info_outside_cwd(self, temp_dir):
        """Test getting info outside CWD is rejected."""
        tool = FileInfoTool()
        result = await tool.execute(path="/etc/passwd")

        assert result.success is False
        assert "denied" in result.error.lower() or "outside" in result.error.lower()
