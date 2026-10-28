"""Small independent consumer of the Aegis Python web delivery profile."""

import os
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import FastAPI, Query

from app import __version__
from app.telemetry import Telemetry, TelemetryMiddleware

# Public status only; no user-controlled URL, forwarded credentials or provider response body.
PORTAL_STATUS = "http://aegis-portal.aegis-portal-system.svc.cluster.local/api/v1/status"

# The portal validates its reviewed public authority even on private service requests.
PORTAL_HOST = os.getenv("AEGIS_PORTAL_HOST", "localhost:8443")


@asynccontextmanager
async def lifespan(app):
    app.state.telemetry = (
        Telemetry("hello-aegis", __version__) if os.getenv("KUBERNETES_SERVICE_HOST") else None
    )
    try:
        yield
    finally:
        if app.state.telemetry:
            app.state.telemetry.close()
            app.state.telemetry = None


app = FastAPI(
    title="Hello Aegis", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
)
app.state.telemetry = None
app.add_middleware(TelemetryMiddleware, holder=app)


@app.get("/")
def greeting():
    return {
        "app": "hello-aegis",
        "message": "Hello from an application deployed by Aegis",
        "version": __version__,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"app": "hello-aegis", "version": __version__}


@app.get("/api/echo")
def echo(message: Annotated[str, Query(min_length=1, max_length=120)]):
    return {"message": message}


@app.get("/api/portal-status")
def portal_status():
    telemetry = app.state.telemetry
    if telemetry is None:
        return {"telemetry": "disabled", "portal_status_code": None}
    with telemetry.client_span("GET portal status", "aegis-portal") as span:
        headers = {"Host": PORTAL_HOST}
        telemetry.propagator.inject(headers)
        try:
            with httpx.Client(timeout=2, trust_env=False, follow_redirects=False) as client:
                with client.stream("GET", PORTAL_STATUS, headers=headers) as response:
                    status = response.status_code
            span.set_attribute("http.response.status_code", status)
            return {"portal_status_code": status}
        except httpx.HTTPError:
            from opentelemetry.trace import Status, StatusCode

            span.set_status(Status(StatusCode.ERROR))
            return {"portal_status_code": None, "telemetry": "portal_unavailable"}
