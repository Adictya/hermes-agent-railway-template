import hashlib
import hmac
import json
import logging
import os
import time
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
LINEAR_ROUTE_PREFIX = "linear-"
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
logger = logging.getLogger(__name__)


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
    port = os.environ.get("DASHBOARD_PORT", "8081")
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


def linear_webhook_secret() -> str:
    return merged_env().get("LINEAR_WEBHOOK_SECRET", "")


def linear_webhook_max_age_seconds() -> int | None:
    value = merged_env().get("LINEAR_WEBHOOK_MAX_AGE_SECONDS", "60").strip()
    if not value:
        return 60
    try:
        max_age = int(value)
    except ValueError:
        logger.warning(
            "Invalid LINEAR_WEBHOOK_MAX_AGE_SECONDS=%r, defaulting to 60",
            value,
        )
        return 60
    return max_age if max_age > 0 else None


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
    body: bytes | None = None,
    header_overrides: dict[str, str] | None = None,
    stripped_headers: set[str] | None = None,
):
    client: httpx.AsyncClient = request.app.state.client
    target_url = build_target_url(base_url, path, request.url.query)
    headers = build_upstream_headers(request, forwarded_prefix=forwarded_prefix)
    if stripped_headers:
        stripped = {header_name.lower() for header_name in stripped_headers}
        headers = {
            name: value
            for name, value in headers.items()
            if name.lower() not in stripped
        }
    if header_overrides:
        headers.update(header_overrides)
    if body is None:
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
        logger.error(
            "Failed forwarding %s to %s: %s", request.url.path, target_url, exc
        )
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


def is_linear_webhook_route(subpath: str) -> bool:
    return subpath.startswith(LINEAR_ROUTE_PREFIX)


def is_linear_webhook_request(request: Request, subpath: str) -> bool:
    return is_linear_webhook_route(subpath) or "linear-signature" in request.headers


def compute_linear_signature(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def verify_linear_signature(
    signature: str | None, secret: str, raw_body: bytes
) -> str | None:
    if not signature:
        return None
    expected = compute_linear_signature(secret, raw_body)
    if hmac.compare_digest(signature.strip().lower(), expected):
        return expected
    return None


def parse_linear_payload(raw_body: bytes) -> dict | None:
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def extract_linear_event(request: Request, payload: dict | None) -> str | None:
    header_event = request.headers.get("linear-event", "").strip()
    payload_type = str((payload or {}).get("type", "")).strip()
    payload_action = str((payload or {}).get("action", "")).strip()

    event_name = header_event or payload_type
    if event_name and payload_action:
        return f"{event_name}.{payload_action}"
    return event_name or payload_action or None


def is_stale_linear_webhook(payload: dict | None, max_age_seconds: int | None) -> bool:
    if not payload or max_age_seconds is None:
        return False

    webhook_timestamp = payload.get("webhookTimestamp")
    if webhook_timestamp in (None, ""):
        return False

    try:
        timestamp = float(webhook_timestamp)
    except (TypeError, ValueError):
        logger.warning("Invalid Linear webhookTimestamp=%r", webhook_timestamp)
        return True

    # Linear documents webhookTimestamp in milliseconds. Accept seconds too if
    # a client ever sends them, then compare against the current wall clock.
    if timestamp < 1_000_000_000_000:
        timestamp *= 1000

    return abs(time.time() * 1000 - timestamp) > max_age_seconds * 1000


async def linear_webhook(request: Request, subpath: str):
    secret = linear_webhook_secret()
    if not secret:
        logger.error(
            "LINEAR_WEBHOOK_SECRET is not set; refusing Linear webhook for %s",
            request.url.path,
        )
        return JSONResponse(
            {"error": "LINEAR_WEBHOOK_SECRET is not configured"},
            status_code=503,
        )

    # Signature verification must use the exact raw body bytes Linear sent.
    # Parsing and re-serializing JSON can change formatting and break HMAC checks.
    raw_body = await request.body()
    incoming_signature = request.headers.get("linear-signature")
    forwarded_signature = verify_linear_signature(incoming_signature, secret, raw_body)
    if not forwarded_signature:
        logger.warning(
            "Rejected Linear webhook for %s from %s: missing or invalid signature",
            request.url.path,
            request.client.host if request.client else "unknown",
        )
        return JSONResponse({"error": "Invalid Linear signature"}, status_code=401)

    payload = parse_linear_payload(raw_body)
    if payload is None:
        logger.warning(
            "Linear webhook for %s had a valid signature but malformed JSON; forwarding raw body",
            request.url.path,
        )
    elif is_stale_linear_webhook(payload, linear_webhook_max_age_seconds()):
        logger.warning(
            "Rejected stale Linear webhook for %s from %s",
            request.url.path,
            request.client.host if request.client else "unknown",
        )
        return JSONResponse({"error": "Stale Linear webhook"}, status_code=401)

    header_overrides = {
        "X-Webhook-Signature": forwarded_signature,
        "X-Webhook-Provider": "linear",
        "X-Original-Linear-Signature": incoming_signature or "",
    }
    event_name = extract_linear_event(request, payload)
    if event_name:
        header_overrides["X-Webhook-Event"] = event_name

    delivery_id = request.headers.get("linear-delivery", "").strip()
    if delivery_id:
        header_overrides["X-Webhook-Delivery"] = delivery_id

    return await proxy_request(
        request,
        webhook_base_url(),
        "/webhooks" if not subpath else f"/webhooks/{subpath}",
        body=raw_body,
        header_overrides=header_overrides,
        stripped_headers={
            "Linear-Signature",
            "X-Webhook-Signature",
            "X-Webhook-Provider",
            "X-Webhook-Event",
            "X-Original-Linear-Signature",
            "X-Webhook-Delivery",
        },
    )


async def root(request: Request):
    return JSONResponse({"error": "Not Found"}, status_code=404)


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
    if is_linear_webhook_request(request, subpath):
        return await linear_webhook(request, subpath)

    path = "/webhooks" if not subpath else f"/webhooks/{subpath}"
    return await proxy_request(request, webhook_base_url(), path)


async def default_gateway_passthrough(request: Request):
    subpath = request.path_params.get("path", "")
    path = "/" if not subpath else f"/{subpath}"
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
        Route("/{path:path}", default_gateway_passthrough, methods=ALL_METHODS),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PROXY_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
