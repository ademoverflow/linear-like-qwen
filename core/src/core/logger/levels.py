from __future__ import annotations

import enum
import os


class LogLevel(enum.Enum):
    """LogLevel Enum.

    Defines all the availables levels for logging.
    TODO: maybe define this enum programatically with logging._nameToLevel.
    """

    CRITICAL = 50
    ERROR = 40
    WARNING = 30
    INFO = 20
    DEBUG = 10
    NOTSET = 0

    # Fallback value used as default (see `get_default_value` method.)
    FALLBACK_DEFAULT = INFO

    @classmethod
    def from_str(cls, level: str, fallback: LogLevel) -> LogLevel:
        """Get LogLevel enum from string.

        Args:
            level (str): level name.
            fallback (LogLevel): fallback value if level is not found.

        Returns:
            LogLevel: LogLevel enum.

        """
        try:
            return cls[level]
        except KeyError:
            return fallback

    @classmethod
    def get_default_value(cls) -> LogLevel:
        """Get default log level.

        Returns:
            LogLevel: default log level.

        """
        return cls.from_str(
            os.getenv("LOG_LEVEL", cls.FALLBACK_DEFAULT.name),
            cls.FALLBACK_DEFAULT,
        )
