import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from app.telemetry import Telemetry, TelemetryMiddleware


def instrumented():
    spans = InMemorySpanExporter()
    logs = InMemoryLogRecordExporter()
    metrics = InMemoryMetricReader()
    telemetry = Telemetry(
        "test-app", "test", span_exporter=spans, metric_reader=metrics, log_exporter=logs
    )
    app = FastAPI()
    app.state.telemetry = telemetry
    app.add_middleware(TelemetryMiddleware, holder=app)

    @app.get("/orders/{order_id}")
    def orders(order_id: str):
        return {"ok": True}

    @app.get("/boom")
    def failure():
        raise RuntimeError("sensitive-exception-body")

    @app.get("/health")
    def health():
        return {"ok": True}

    return app, telemetry, spans, logs, metrics


def test_request_signals_use_route_templates_and_never_capture_secrets():
    app, telemetry, spans, logs, metrics = instrumented()
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/orders/private-id?password=private-query",
                headers={
                    "Authorization": "Bearer private-header",
                    "Cookie": "session=private-cookie",
                    "traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01",
                    "tracestate": "vendor=private-state",
                },
            )
            assert response.status_code == 200
            assert client.get("/boom").status_code == 500
            client.get("/health")
        telemetry.flush()
        finished = spans.get_finished_spans()
        assert len(finished) == 2
        first = next(span for span in finished if span.name == "GET /orders/{order_id}")
        assert first.context.trace_id == int("a" * 32, 16)
        assert first.parent.span_id == int("b" * 16, 16)
        assert not first.context.trace_state
        assert (
            next(span for span in finished if span.name == "GET /boom").status.status_code
            == StatusCode.ERROR
        )
        assert all(not span.events for span in finished)
        emitted = logs.get_finished_logs()
        encoded = json.dumps(
            [
                {"body": row.log_record.body, "attributes": dict(row.log_record.attributes)}
                for row in emitted
            ]
        )
        encoded += str([dict(span.attributes) for span in finished])
        for private in [
            "private-id",
            "private-query",
            "private-header",
            "private-cookie",
            "private-state",
            "sensitive-exception-body",
        ]:
            assert private not in encoded
        metric_data = metrics.get_metrics_data()
        names = {
            metric.name
            for resource in metric_data.resource_metrics
            for scope in resource.scope_metrics
            for metric in scope.metrics
        }
        assert {
            "http.server.requests",
            "http.server.request.duration",
            "aegis.telemetry.heartbeat.timestamp",
        } <= names
    finally:
        telemetry.close()


def test_disabled_instrumentation_does_not_affect_business_requests():
    app = FastAPI()
    app.state.telemetry = None
    app.add_middleware(TelemetryMiddleware, holder=app)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_local_walkthrough_does_not_contact_collector_or_portal():
    from app.main import app

    with TestClient(app) as client:
        assert client.get("/api/portal-status").json() == {
            "telemetry": "disabled",
            "portal_status_code": None,
        }


def test_portal_call_propagates_trace_context_without_forwarding_request_secrets(monkeypatch):
    import httpx
    from fastapi import FastAPI

    import app.main as main

    _, telemetry, spans, logs, _ = instrumented()
    _, downstream, downstream_spans, _, _ = instrumented()
    portal = FastAPI()
    portal.state.telemetry = downstream
    portal.add_middleware(TelemetryMiddleware, holder=portal)

    @portal.get("/api/v1/status")
    def status():
        return {"version": "test"}

    seen = []
    real_client = httpx.Client
    with TestClient(portal) as portal_client:

        def transport(request):
            seen.append(request)
            assert str(request.url) == main.PORTAL_STATUS
            assert request.url.scheme == "http" and (request.url.port or 80) == 80
            assert request.headers["host"] == main.PORTAL_HOST
            assert set(request.headers) >= {"traceparent"}
            assert "authorization" not in request.headers and "cookie" not in request.headers
            response = portal_client.get("/api/v1/status", headers=dict(request.headers))
            return httpx.Response(response.status_code, json=response.json())

        monkeypatch.setattr(
            main.httpx,
            "Client",
            lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs),
        )
        try:
            with TestClient(main.app) as client:
                main.app.state.telemetry = telemetry
                response = client.get(
                    "/api/portal-status?secret=private-query",
                    headers={"Authorization": "Bearer private-header", "Cookie": "private-cookie"},
                )
                assert response.json() == {"portal_status_code": 200}
                main.app.state.telemetry = None
            telemetry.flush()
            downstream.flush()
            upstream = spans.get_finished_spans()
            server = next(span for span in upstream if span.name == "GET /api/portal-status")
            child = next(span for span in upstream if span.name == "GET portal status")
            remote = downstream_spans.get_finished_spans()[0]
            assert server.context.trace_id == child.context.trace_id == remote.context.trace_id
            assert child.parent.span_id == server.context.span_id
            assert remote.parent.span_id == child.context.span_id
            assert len(seen) == 1
            encoded = str([dict(s.attributes) for s in upstream])
            encoded += str([row.log_record.body for row in logs.get_finished_logs()])
            for value in ("private-query", "private-header", "private-cookie"):
                assert value not in encoded
        finally:
            main.app.state.telemetry = None
            telemetry.close()
            downstream.close()
