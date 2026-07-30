"""Bounded multi-client WSGI server for a trusted local access point."""

from __future__ import annotations

from socketserver import ThreadingMixIn
import threading
from typing import Any
from wsgiref.simple_server import (
    WSGIRequestHandler,
    WSGIServer,
    make_server,
)


class ContentFreeRequestHandler(WSGIRequestHandler):
    """Do not expose channel names or other request metadata in local logs."""

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class BoundedThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Threaded WSGI server with a fixed in-flight request ceiling."""

    daemon_threads = True
    block_on_close = True
    request_queue_size = 32
    max_workers = 16

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._worker_slots = threading.BoundedSemaphore(self.max_workers)

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self._worker_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._worker_slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._worker_slots.release()


def make_local_server(host: str, port: int, application: Any) -> WSGIServer:
    return make_server(
        host,
        port,
        application,
        server_class=BoundedThreadingWSGIServer,
        handler_class=ContentFreeRequestHandler,
    )
