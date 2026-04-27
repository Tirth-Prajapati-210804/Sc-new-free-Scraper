from __future__ import annotations

import logging

import structlog

from app.core.redaction import redact_log_event, redact_text


class _RedactingFilter(logging.Filter):
    """Redact secrets from any stdlib log record before it leaves the process.

    httpx's INFO logger (and a handful of other libraries) write request URLs
    directly via the stdlib logger, bypassing structlog's processor chain.
    Without this filter the SearchAPI api_key was being printed in plaintext
    on every request — a real secret leak. We re-run redact_text on the
    formatted message so the same patterns we strip from structlog events
    also catch stdlib output.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if record.args:
                record.msg = record.getMessage()
                record.args = ()
            if isinstance(record.msg, str):
                record.msg = redact_text(record.msg)
        except Exception:
            # Never let a redaction error swallow a log line.
            pass
        return True


def configure_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    # Defense in depth: scrub secrets out of any stdlib logger (httpx, asyncio,
    # uvicorn access, etc.) before they hit the handler.
    root_logger = logging.getLogger()
    if not any(isinstance(f, _RedactingFilter) for f in root_logger.filters):
        root_logger.addFilter(_RedactingFilter())
    for handler in root_logger.handlers:
        if not any(isinstance(f, _RedactingFilter) for f in handler.filters):
            handler.addFilter(_RedactingFilter())

    # httpx logs every outbound request at INFO with the full URL. We already
    # emit structured `searchapi_*` events with non-sensitive fields, so the
    # raw httpx line is pure noise and a secret-leak risk. Quiet it.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            redact_log_event,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
