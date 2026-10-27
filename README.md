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
