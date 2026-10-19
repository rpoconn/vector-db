"""Retry policy shared by all external I/O (downloads, model fetches, SMTP)."""

import logging
from collections.abc import Callable

from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


def retrying(
    is_retryable: Callable[[BaseException], bool],
    *,
    attempts: int = 5,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
) -> Retrying:
    """Exponential-backoff retry policy that re-raises the last error once attempts run out.

    Call the result directly (`policy(fn, *args)`) or iterate it (`for attempt in policy:`).
    """
    return Retrying(
        retry=retry_if_exception(is_retryable),
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=min_wait, min=min_wait, max=max_wait),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
