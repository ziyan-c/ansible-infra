from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlencode

import httpx
from fastapi import Request, Response


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def _filtered_headers(items: Iterable[tuple[str, str]]) -> dict[str, str]:
    return {key: value for key, value in items if key.lower() not in HOP_BY_HOP_HEADERS}


def join_url(base_url: str, path: str, query: str) -> str:
    clean_path = path.lstrip("/")
    url = f"{base_url.rstrip('/')}/{clean_path}" if clean_path else base_url.rstrip("/")
    if query:
        url = f"{url}?{query}"
    return url


def sanitized_query(request: Request) -> str:
    items = [
        (key, value)
        for key, value in request.query_params.multi_items()
        if key.lower() != "password"
    ]
    return urlencode(items, doseq=True)


async def proxy_request(
    request: Request,
    *,
    client: httpx.AsyncClient,
    base_url: str,
    path: str,
) -> Response:
    upstream_url = join_url(base_url, path, sanitized_query(request))
    body = await request.body()
    upstream = await client.request(
        request.method,
        upstream_url,
        content=body,
        headers=_filtered_headers(request.headers.items()),
    )
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=_filtered_headers(upstream.headers.items()),
        media_type=upstream.headers.get("content-type"),
    )
