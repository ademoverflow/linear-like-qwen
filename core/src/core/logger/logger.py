import json
import logging
import sys
from datetime import UTC, datetime

from .levels import LogLevel


class CustomFormatter(logging.Formatter):
    """Custom Formatter."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        """Format time.

        Args:
            record (logging.LogRecord): Log record.
            datefmt (Optional[str], optional): Date format. Defaults to None.

        Returns:
            str: Formatted time.

        """
        log_timestamp = record.created
        current_datetime = datetime.fromtimestamp(log_timestamp, tz=UTC)

        if datefmt:
            return current_datetime.strftime(datefmt)

        return current_datetime.isoformat()


class JSONFormatter(logging.Formatter):
    """JSON Formatter for structured logging."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        """Format time.

        Args:
            record (logging.LogRecord): Log record.
            datefmt (Optional[str], optional): Date format. Defaults to None.

        Returns:
            str: Formatted time.

        """
        log_timestamp = record.created
        current_datetime = datetime.fromtimestamp(log_timestamp, tz=UTC)

        if datefmt:
            return current_datetime.strftime(datefmt)

        return current_datetime.isoformat()

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON.

        Args:
            record (logging.LogRecord): Log record.

        Returns:
            str: JSON formatted log message.

        """
        log_data = {
            "timestamp": self.formatTime(record),
            "log_level": record.levelname,
            "logger_name": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_data)


def get_logger(
    name: str, log_level: LogLevel | None = None, *, json_logging: bool = False
) -> logging.Logger:
    """Get logger.

    Args:
        name (str): Name of the logger.
        log_level (LogLevel | None, optional): Log level. Defaults to None.
        json_logging (bool, optional): Enable JSON logging format. Defaults to False.

    Returns:
        logging.Logger: Logger.

    """
    _logger = logging.getLogger(name)
    _logger.propagate = False

    # Some explanation of why this check is made:
    #   When you instantiate two or more loggers with the same name,
    #   you only get a reference of the first one.
    #   So, adding multiple handlers to same logger has a bad consequence:
    #   printing a line as many times as there are logger instantiated.
    #   That's why we check for handlers before adding it.

    if not _logger.hasHandlers():
        _logger.handlers = []

        if json_logging:
            formatter: logging.Formatter = JSONFormatter()
        else:
            log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
            formatter = CustomFormatter(log_format)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        _logger.addHandler(handler)

    if not log_level:
        log_level = LogLevel.get_default_value()

    _logger.setLevel(log_level.value)

    return _logger
