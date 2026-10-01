"""Capture payload-safe ingestion messages for one import request."""

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone


_active_capture = ContextVar('active_import_log_capture', default=None)


class _ImportLogHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def emit(self, record):
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
def capture_lib_logs(emit):
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
