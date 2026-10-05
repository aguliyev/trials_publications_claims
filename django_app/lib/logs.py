"""Shared, payload-safe logging for the ingestion pipeline."""

import logging
import os
import traceback
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable


DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
DEFAULT_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
_call_depth = ContextVar("pipeline_logging_depth", default=0)


def get_logger(name: str, level: str | int | None = None, formatter: str | None = None) -> logging.Logger:
    """Return a module logger; optionally configure its level and console format."""
    logger = logging.getLogger(name)
    logger.setLevel(DEFAULT_LEVEL if level is None else level)
    if formatter is not None:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(formatter))
        logger.addHandler(handler)
        logger.propagate = False
    return logger


def _summary(value: Any) -> str:
    """Never render payloads or object reprs (which may contain credentials/text)."""
    if value is None or isinstance(value, bool):
        return type(value).__name__
    if isinstance(value, (str, bytes)):
        return type(value).__name__
    if isinstance(value, (list, tuple, dict, set)):
        return f"{type(value).__name__}(len={len(value)})"
    if isinstance(value, (int, float)):
        return type(value).__name__
    return type(value).__name__


def logged(func: Callable[..., Any]) -> Callable[..., Any]:
    """Log calls and results at DEBUG, failures at ERROR, without changing behavior."""
    logger = get_logger(func.__module__)

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        depth = _call_depth.get()
        token = _call_depth.set(depth + 1)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("%s called args=%s kwargs=%s", func.__name__,
                         [_summary(arg) for arg in args],
                         {key: _summary(value) for key, value in kwargs.items()})
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            if depth == 0:
                frames = [(frame.name, frame.lineno) for frame in traceback.extract_tb(exc.__traceback__)]
                logger.error("%s failed error_type=%s frames=%s", func.__name__, type(exc).__name__, frames)
            raise
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("%s returned %s", func.__name__, _summary(result))
            return result
        finally:
            _call_depth.reset(token)

    return wrapper
