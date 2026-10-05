"""Capture payload-safe ingestion messages for one import request."""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any


_active_capture = ContextVar('active_import_log_capture', default=None)


class _ImportLogHandler(logging.Handler):
    def __init__(self, callback: Callable[[dict[str, str]], Any]) -> None:
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        if _active_capture.get() is not self.callback \
                or not record.name.startswith('lib.') \
                or record.levelno not in (logging.INFO, logging.WARNING, logging.ERROR):
            return
        message = record.getMessage().split(' frames=', 1)[0].splitlines()[0][:1000]
        self.callback({
            'level': record.levelname,
            'message': message,
            'time': datetime.fromtimestamp(record.created, timezone.utc).isoformat().replace('+00:00', 'Z'),
        })


@contextmanager
def capture_lib_logs(emit: Callable[[dict[str, str]], Any]) -> Iterator[None]:
    """Forward this context's lib.* records without mixing concurrent requests."""
    handler = _ImportLogHandler(emit)
    logger = logging.getLogger('lib')
    token = _active_capture.set(emit)
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        _active_capture.reset(token)
