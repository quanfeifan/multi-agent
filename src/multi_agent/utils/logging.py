"""Logging configuration for multi-agent framework.

This module provides structured logging with JSON output support.
"""

import logging
import sys
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class LogLevel(str, Enum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogEntry(BaseModel):
    """Structured log entry.

    Attributes:
        timestamp: Log timestamp
        level: Log level
        message: Log message
        logger: Logger name
        context: Additional context
    """

    timestamp: str
    level: str
    message: str
    logger: str
    context: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return self.model_dump()


class StructuredFormatter(logging.Formatter):
    """Formatter for structured log output.

    Outputs logs in JSON format for parsing and analysis.
    """

    def __init__(self, format_type: str = "json") -> None:
        """Initialize the structured formatter.

        Args:
            format_type: Output format ("json" or "text")
        """
        super().__init__()
        self.format_type = format_type

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record.

        Args:
            record: Log record to format

        Returns:
            Formatted log string
        """
        log_entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created).isoformat(),
            level=record.levelname,
            message=record.getMessage(),
            logger=record.name,
            context={
                "function": record.funcName,
                "line": record.lineno,
                "module": record.module,
                "path": record.pathname,
            },
        )

        # Add exception info if present
        if record.exc_info:
            log_entry.context["exception"] = self.formatException(record.exc_info)

        if self.format_type == "json":
            import json

            return json.dumps(log_entry.to_dict())
        else:
            # Text format
            return f"{log_entry.timestamp} [{log_entry.level}] {log_entry.logger}: {log_entry.message}"


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for better readability.

    Uses ANSI color codes for terminal output.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with colors.

        Args:
            record: Log record to format

        Returns:
            Formatted log string with colors
        """
        level_color = self.COLORS.get(record.levelname, "")
        reset_color = self.COLORS["RESET"]

        # Format: [LEVEL] logger: message
        level_name = f"{level_color}{record.levelname}{reset_color}"
        return f"[{level_name}] {record.name}: {record.getMessage()}"


def setup_logging(
    level: str | LogLevel = "INFO",
    format_type: str = "text",
    use_colors: bool = True,
    log_file: str | None = None,
) -> None:
    """Set up logging for the multi-agent framework.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Output format ("json", "text")
        use_colors: Whether to use colors in console output
        log_file: Optional file to write logs to
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper() if isinstance(level, str) else level.value))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)

    if use_colors and format_type == "text":
        console_handler.setFormatter(ColoredFormatter())
    elif format_type == "json":
        console_handler.setFormatter(StructuredFormatter(format_type="json"))
    else:
        console_handler.setFormatter(StructuredFormatter(format_type="text"))

    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredFormatter(format_type=format_type))
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (usually __name__ of the module)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggerContext:
    """Context manager for adding context to log messages.

    Allows temporary addition of contextual information to log records.

    Args:
        logger: Logger instance
        context: Context dictionary to add

    Example:
        with LoggerContext(logger, {"task_id": "123"}):
            logger.info("Processing task")  # Will include task_id in context
    """

    def __init__(self, logger: logging.Logger, context: dict[str, Any]) -> None:
        """Initialize the logger context.

        Args:
            logger: Logger instance
            context: Context to add
        """
        self.logger = logger
        self.context = context
        self.old_factory: Any = None

    def __enter__(self) -> "LoggerContext":
        """Enter the context.

        Returns:
            Self
        """
        self.old_factory = self.logger.makeRecord

        def make_record_with_context(
            name: str,
            level: int,
            fn: str,
            lno: int,
            msg: str,
            args: Any,
            exc_info: Any,
            func: str | None = None,
            extra: dict[str, Any] | None = None,
        ) -> logging.LogRecord:
            """Create a log record with added context."""
            record = self.old_factory(  # type: ignore
                name, level, fn, lno, msg, args, exc_info, func, extra
            )
            # Add context to record
            if not hasattr(record, "context"):
                record.context = {}
            record.context.update(self.context)
            return record

        self.logger.makeRecord = make_record_with_context
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context.

        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        if self.old_factory:
            self.logger.makeRecord = self.old_factory


# Initialize default logging
setup_logging()
