import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

HERMES_HOME = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
ENV_FILE_PATH = Path(HERMES_HOME) / ".env"
ALL_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
}


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    result = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        result[key] = value
    return result


def merged_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(read_env_file(ENV_FILE_PATH))
    return env


def normalize_local_host(host: str | None, default: str) -> str:
    if not host or host == "0.0.0.0":
        return default
    return host


def dashboard_base_url() -> str:
    port = os.environ.get("PORT", "8081")
    return f"http://127.0.0.1:{port}"


def api_server_base_url() -> str:
    env = merged_env()
    host = normalize_local_host(env.get("API_SERVER_HOST"), "127.0.0.1")
    port = env.get("API_SERVER_PORT", "8642")
    return f"http://{host}:{port}"


def webhook_base_url() -> str:
    env = merged_env()
    port = env.get("WEBHOOK_PORT", "8644")
    return f"http://127.0.0.1:{port}"


def build_target_url(base_url: str, path: str, query: str) -> str:
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        return f"{url}?{query}"
    return url


def build_upstream_headers(
    request: Request, forwarded_prefix: str | None = None
) -> dict[str, str]:
    headers = {}
    for name, value in request.headers.items():
        lower_name = name.lower()
        if lower_name == "host" or lower_name in HOP_BY_HOP_HEADERS:
            continue
        headers[name] = value

    client_host = request.client.host if request.client else ""
    existing_forwarded_for = request.headers.get("x-forwarded-for", "")
    forwarded_for = ", ".join(
        part for part in (existing_forwarded_for, client_host) if part
    )
    if forwarded_for:
        headers["X-Forwarded-For"] = forwarded_for
    if request.headers.get("host"):
        headers["X-Forwarded-Host"] = request.headers["host"]
    headers["X-Forwarded-Proto"] = request.url.scheme
    if forwarded_prefix:
        headers["X-Forwarded-Prefix"] = forwarded_prefix
    return headers


async def proxy_request(
    request: Request,
    base_url: str,
    path: str,
    *,
    forwarded_prefix: str | None = None,
):
    client: httpx.AsyncClient = request.app.state.client
    target_url = build_target_url(base_url, path, request.url.query)
    headers = build_upstream_headers(request, forwarded_prefix=forwarded_prefix)
    body = await request.body()

    upstream_request = client.build_request(
        request.method,
        target_url,
        headers=headers,
        content=body,
    )

    try:
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.HTTPError as exc:
        return JSONResponse(
            {
                "error": "Upstream unavailable",
                "target": target_url,
                "detail": str(exc),
            },
            status_code=503,
        )

    response = StreamingResponse(
        upstream_response.aiter_raw(),
        status_code=upstream_response.status_code,
        background=BackgroundTask(upstream_response.aclose),
    )
    response.raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in upstream_response.headers.multi_items()
        if name.lower() not in HOP_BY_HOP_HEADERS
    ]
    return response


async def root(request: Request):
    return JSONResponse(
        {
            "service": "hermes gateway proxy",
            "dashboard": "/configure",
            "dashboard_api": "/api",
            "gateway_api": "/v1",
            "webhooks": "/webhooks",
            "health": "/health",
        }
    )


async def health(request: Request):
    return await proxy_request(request, dashboard_base_url(), "/health")


async def configure(request: Request):
    subpath = request.path_params.get("path", "")
    path = "/" if not subpath else f"/{subpath}"
    return await proxy_request(
        request,
        dashboard_base_url(),
        path,
        forwarded_prefix="/configure",
    )


async def dashboard_api(request: Request):
    subpath = request.path_params.get("path", "")
    path = "/api" if not subpath else f"/api/{subpath}"
    return await proxy_request(request, dashboard_base_url(), path)


async def gateway_api(request: Request):
    subpath = request.path_params.get("path", "")
    path = "/v1" if not subpath else f"/v1/{subpath}"
    return await proxy_request(request, api_server_base_url(), path)


async def webhooks(request: Request):
    subpath = request.path_params.get("path", "")
    path = "/webhooks" if not subpath else f"/webhooks/{subpath}"
    return await proxy_request(request, webhook_base_url(), path)


@asynccontextmanager
async def lifespan(app):
    timeout = httpx.Timeout(connect=5.0, read=None, write=None, pool=None)
    app.state.client = httpx.AsyncClient(timeout=timeout)
    yield
    await app.state.client.aclose()


app = Starlette(
    routes=[
        Route("/", root),
        Route("/health", health),
        Route("/configure", configure, methods=ALL_METHODS),
        Route("/configure/{path:path}", configure, methods=ALL_METHODS),
        Route("/api", dashboard_api, methods=ALL_METHODS),
        Route("/api/{path:path}", dashboard_api, methods=ALL_METHODS),
        Route("/v1", gateway_api, methods=ALL_METHODS),
        Route("/v1/{path:path}", gateway_api, methods=ALL_METHODS),
        Route("/webhooks", webhooks, methods=ALL_METHODS),
        Route("/webhooks/{path:path}", webhooks, methods=ALL_METHODS),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PROXY_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
