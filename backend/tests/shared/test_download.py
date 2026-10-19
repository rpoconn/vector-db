from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from app.shared.download import IncompleteDownloadError, download_file

URL = "https://example.test/archive.tar"
PAYLOAD = bytes(range(256)) * 40


class _BrokenStream(httpx.SyncByteStream):
    """Yields part of the body, then drops the connection."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def __iter__(self) -> Iterator[bytes]:
        yield self._data
        raise httpx.ReadError("connection reset")


class FakeServer:
    """Serves PAYLOAD with Range support; the first `failures` GETs break halfway."""

    def __init__(self, *, failures: int = 0, honor_range: bool = True) -> None:
        self.failures = failures
        self.honor_range = honor_range
        self.ranges: list[str | None] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        headers = {"content-length": str(len(PAYLOAD))}
        if request.method == "HEAD":
            return httpx.Response(200, headers=headers)
        self.ranges.append(request.headers.get("range"))
        start = 0
        if self.honor_range and request.headers.get("range"):
            start = int(request.headers["range"].removeprefix("bytes=").rstrip("-"))
        body = PAYLOAD[start:]
        status = 206 if start else 200
        if self.failures:
            self.failures -= 1
            return httpx.Response(status, stream=_BrokenStream(body[: len(body) // 2]))
        return httpx.Response(status, content=body)


def _download(server: FakeServer, destination: Path, attempts: int = 3) -> Path:
    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        return download_file(client, URL, destination, attempts=attempts, min_wait=0)


def test_downloads_complete_file(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "archive.tar"
    server = FakeServer()

    assert _download(server, destination) == destination
    assert destination.read_bytes() == PAYLOAD
    assert not destination.with_name("archive.tar.part").exists()
    assert server.ranges == [None]


def test_resumes_after_dropped_connection(tmp_path: Path) -> None:
    destination = tmp_path / "archive.tar"
    server = FakeServer(failures=1)

    _download(server, destination)

    assert destination.read_bytes() == PAYLOAD
    assert server.ranges == [None, f"bytes={len(PAYLOAD) // 2}-"]


def test_restarts_when_server_ignores_range(tmp_path: Path) -> None:
    destination = tmp_path / "archive.tar"
    destination.with_name("archive.tar.part").write_bytes(PAYLOAD[:100])

    _download(FakeServer(honor_range=False), destination)

    assert destination.read_bytes() == PAYLOAD


def test_skips_when_already_complete(tmp_path: Path) -> None:
    destination = tmp_path / "archive.tar"
    destination.write_bytes(PAYLOAD)
    server = FakeServer()

    _download(server, destination)

    assert server.ranges == []


def test_gives_up_after_attempts(tmp_path: Path) -> None:
    destination = tmp_path / "archive.tar"

    with pytest.raises(httpx.ReadError):
        _download(FakeServer(failures=5), destination, attempts=2)

    assert not destination.exists()
    assert destination.with_name("archive.tar.part").exists()


def test_rejects_short_body(tmp_path: Path) -> None:
    def short(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-length": "10"})
        return httpx.Response(200, content=b"abc")

    with (
        httpx.Client(transport=httpx.MockTransport(short)) as client,
        pytest.raises(IncompleteDownloadError),
    ):
        download_file(client, URL, tmp_path / "x", attempts=2, min_wait=0)


def test_does_not_retry_client_errors(tmp_path: Path) -> None:
    calls: list[str] = []

    def not_found(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(404)

    with (
        httpx.Client(transport=httpx.MockTransport(not_found)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        download_file(client, URL, tmp_path / "x", attempts=3, min_wait=0)

    assert calls == ["HEAD"]
