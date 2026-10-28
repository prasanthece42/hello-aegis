# Hello Aegis

An independent Python 3.12 test service managed by Aegis. Public source is separate from
the portal and existing sample. Delivery targets DEV in local Kind; publishing the source
does not create a cloud endpoint. No App keys, deployment credentials or kubeconfig are
included in this application.

Endpoints: `/` identifies the app/version, `/health` implements the exact platform health
contract, `/version` reports the application version, and `/api/echo?message=hello` accepts
a bounded message.

```sh
uv sync --locked
uv run --locked pytest -q
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

CI and release call the approved immutable Aegis workflow/helper family. Both CPU
architectures must pass tests/scans/runtime smoke before publication. Release assets
include schema-3 source-bound evidence and the full OCI graph. The portal registration,
reviewed catalog, verified local cache, scoped GitOps PR and Argo rollout remain separate
delivery steps. PROD still requires independent human approval and operator sync.


## Instrumentation candidate (1.1.0)

The candidate emits OpenTelemetry request counts, durations, heartbeat, sanitized logs and
server spans when running inside Kubernetes. Local walkthroughs leave exporters disabled.
The collector address is fixed to the private Aegis service; the application receives no
query credentials or Kubernetes API access.

`GET /api/portal-status` makes a bounded request to the configured portal's fixed public
status endpoint and propagates W3C trace context. It forwards no incoming cookies, auth
headers, queries or request bodies, follows no redirects, and returns only the status code.
Without telemetry it reports `telemetry: disabled` and makes no outbound request. Health
checks remain unchanged. Ordinary request telemetry uses route templates and excludes raw
queries, headers, bodies, exception messages and health probes.

Tests verify emitted metrics/logs/spans and a real in-process HTTP request through hello-aegis
and an instrumented portal fixture, including parent/child span relationships and credential
exclusion. This establishes local instrumentation behavior, not deployed end-to-end ingestion.
The telemetry stack and immutable 1.1.0 release need review before the existing DEV deployment
can be updated. Publishing source alone does not change it.
