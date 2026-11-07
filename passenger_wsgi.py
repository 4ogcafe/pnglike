"""
Passenger WSGI Entrypoint for PngLike Studio
Used by cPanel / CloudLinux / Hostinger "Setup Python App" (Phusion Passenger).
Includes a self-contained, high-performance ASGI-to-WSGI bridge so FastAPI runs
natively without requiring external pip packages like a2wsgi.
"""
import os
import sys
import asyncio
from pathlib import Path

# Ensure local venv and project root are in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Auto-detect virtualenv site-packages if present
for p in BASE_DIR.glob(".venv/lib/python*/site-packages"):
    if p.is_dir():
        sys.path.insert(0, str(p))
        break

from app import app

# 1. Prefer a2wsgi if installed in environment
try:
    from a2wsgi import ASGIMiddleware
    application = ASGIMiddleware(app)
except ImportError:
    # 2. Built-in Pure Python ASGI-to-WSGI Adapter
    def application(environ, start_response):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        headers = []
        for k, v in environ.items():
            if k.startswith("HTTP_"):
                header_name = k[5:].lower().replace("_", "-").encode("latin1")
                headers.append((header_name, v.encode("latin1")))
            elif k in ("CONTENT_TYPE", "CONTENT_LENGTH") and v:
                headers.append((k.lower().replace("_", "-").encode("latin1"), v.encode("latin1")))

        path = environ.get("PATH_INFO", "") or "/"
        query_string = environ.get("QUERY_STRING", "").encode("latin1")
        method = environ.get("REQUEST_METHOD", "GET")

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "path": path,
            "raw_path": path.encode("latin1"),
            "query_string": query_string,
            "headers": headers,
            "client": (environ.get("REMOTE_ADDR", "127.0.0.1"), int(environ.get("REMOTE_PORT", "0") or 0)),
            "server": (environ.get("SERVER_NAME", "127.0.0.1"), int(environ.get("SERVER_PORT", "80") or 80)),
        }

        status_code = [200]
        status_text = ["OK"]
        response_headers = []
        body_chunks = []

        try:
            content_length = int(environ.get("CONTENT_LENGTH") or 0)
        except (ValueError, TypeError):
            content_length = 0

        input_body = environ["wsgi.input"].read(content_length) if content_length > 0 and "wsgi.input" in environ else b""
        body_sent = [False]

        async def receive():
            if not body_sent[0]:
                body_sent[0] = True
                return {"type": "http.request", "body": input_body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
                for k, v in message.get("headers", []):
                    response_headers.append((k.decode("latin1"), v.decode("latin1")))
            elif message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))

        try:
            loop.run_until_complete(app(scope, receive, send))
        finally:
            loop.close()

        status_str = f"{status_code[0]} OK"
        start_response(status_str, response_headers)
        return body_chunks
