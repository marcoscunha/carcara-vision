import logging
import sys
from typing import Any
from typing import Dict

# Logging configuration
LOGGING_CONFIG: Dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "detailed",
            "stream": sys.stdout,
        },
        "file": {
            "class": "logging.FileHandler",
            "formatter": "detailed",
            "filename": "app.log",
            "mode": "a",
        },
    },
    "loggers": {
        "": {  # Root logger
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "uvicorn": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "fastapi": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "sqlalchemy.engine": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "websockets": {
            "handlers": ["console", "file"],
            "level": "INFO",  # Change from DEBUG to INFO to suppress debug messages
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["console", "file"],
            "level": "INFO",  # Adjust level if needed
            "propagate": False,
        },
    },
}


def setup_logging():
    """Configure logging for the application."""
    # logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger(__name__)
    logger.info("Logging configured successfully")
