"""Resumable, size-verified HTTP file downloads."""

import logging
from pathlib import Path

import httpx

from app.shared.retry import retrying

logger = logging.getLogger(__name__)

_PROGRESS_STEP_PERCENT = 10


class IncompleteDownloadError(Exception):
    """The transfer ended before the expected number of bytes arrived."""


def is_transient_download_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return isinstance(exc, httpx.TransportError | IncompleteDownloadError)


def download_file(
    client: httpx.Client,
    url: str,
    destination: Path,
    *,
    attempts: int = 5,
    min_wait: float = 1.0,
) -> Path:
    """Download `url` to `destination`, resuming a previous partial download if present.

    Bytes are written to `<destination>.part` and renamed only once the size matches the
    server's Content-Length, so an existing `destination` is always complete. Idempotent.
    """
    policy = retrying(is_transient_download_error, attempts=attempts, min_wait=min_wait)
    total = policy(_remote_size, client, url)

    if destination.exists() and destination.stat().st_size == total:
        logger.info("%s already downloaded (%d bytes)", destination.name, total)
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    policy(_download_remaining, client, url, partial, total)
    partial.replace(destination)
    logger.info("Downloaded %s (%d bytes)", destination.name, total)
    return destination


def _remote_size(client: httpx.Client, url: str) -> int:
    response = client.head(url, follow_redirects=True)
    response.raise_for_status()
    return int(response.headers["content-length"])


def _download_remaining(client: httpx.Client, url: str, partial: Path, total: int) -> None:
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > total:
        logger.warning("Discarding oversized partial file %s", partial.name)
        offset = 0
    if offset < total:
        if offset:
            logger.info("Resuming %s at byte %d of %d", partial.name, offset, total)
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        with client.stream("GET", url, headers=headers, follow_redirects=True) as response:
            response.raise_for_status()
            if response.status_code != httpx.codes.PARTIAL_CONTENT:
                offset = 0  # Server ignored the range request; start over.
            progress = _ProgressLogger(partial.name, total, offset)
            with partial.open("ab" if offset else "wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)
                    progress.advance(len(chunk))

    size = partial.stat().st_size
    if size != total:
        raise IncompleteDownloadError(f"{partial.name}: got {size} of {total} bytes")


class _ProgressLogger:
    def __init__(self, name: str, total: int, done: int) -> None:
        self._name = name
        self._total = max(total, 1)
        self._done = done
        self._next_percent = self._percent() + _PROGRESS_STEP_PERCENT

    def _percent(self) -> int:
        return self._done * 100 // self._total

    def advance(self, size: int) -> None:
        self._done += size
        if self._percent() >= self._next_percent:
            logger.info("%s: %d%%", self._name, self._percent())
            self._next_percent = self._percent() + _PROGRESS_STEP_PERCENT
