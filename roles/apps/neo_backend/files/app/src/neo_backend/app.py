from __future__ import annotations

import asyncio

import httpx
import uvicorn
from fastapi import Depends, FastAPI, Request

from .auth import require_proxy_auth
from .config import Settings
from .proxy import proxy_request
from .tunnel import SSHTunnelManager


def create_proxy_app(
    settings: Settings | None = None,
    *,
    service_name: str,
    upstream_base_url: str,
    tunnel: SSHTunnelManager | None = None,
) -> FastAPI:
    resolved = settings or Settings.from_env()
    resolved.validate()
    app = FastAPI(title=f"Neo Backend Temporary ({service_name})")

    def auth_dependency(request: Request) -> None:
        require_proxy_auth(request, resolved)

    @app.on_event("startup")
    async def startup() -> None:
        app.state.http = httpx.AsyncClient(timeout=resolved.upstream_timeout_seconds)

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await app.state.http.aclose()

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "ok": True,
            "service": service_name,
            "upstream_base_url": upstream_base_url,
            "tunnel": tunnel.status() if tunnel else {"enabled": resolved.manage_ssh_tunnel},
        }

    @app.get("/auth/check")
    async def auth_check(_: None = Depends(auth_dependency)) -> dict[str, object]:
        return {
            "ok": True,
            "authenticated": True,
            "service": service_name,
        }

    @app.api_route("/", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def service_proxy(
        request: Request,
        path: str = "",
        _: None = Depends(auth_dependency),
    ):
        return await proxy_request(
            request,
            client=request.app.state.http,
            base_url=upstream_base_url,
            path=path,
        )

    return app


async def serve(settings: Settings) -> None:
    settings.validate()
    tunnel = SSHTunnelManager(settings)
    if settings.log_tunnel_command and settings.manage_ssh_tunnel:
        print(f"Starting SSH tunnel: {tunnel.masked_command()}")
    await tunnel.start()

    rag_app = create_proxy_app(
        settings,
        service_name="rag",
        upstream_base_url=settings.rag_base_url,
        tunnel=tunnel,
    )
    llm_app = create_proxy_app(
        settings,
        service_name="llm",
        upstream_base_url=settings.llm_base_url,
        tunnel=tunnel,
    )
    rag_server = uvicorn.Server(
        uvicorn.Config(rag_app, host=settings.bind_host, port=settings.rag_proxy_port)
    )
    llm_server = uvicorn.Server(
        uvicorn.Config(llm_app, host=settings.bind_host, port=settings.llm_proxy_port)
    )

    try:
        await asyncio.gather(rag_server.serve(), llm_server.serve())
    finally:
        await tunnel.stop()


def main() -> None:
    settings = Settings.from_env()
    asyncio.run(serve(settings))


if __name__ == "__main__":
    main()
