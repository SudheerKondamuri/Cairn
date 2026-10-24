# Cairn submission walkthrough (target: 2:30–3:00)

## 0:00–0:20 — Problem and safety boundary

Show the repository README architecture diagram. Say:

> Cairn takes a security report and supplied source, runs the target only inside
> a fresh Celesto Cloud guest, and returns evidence-backed `verified`,
> `not_reproduced`, or `inconclusive`—never a universal safety claim.

## 0:20–0:45 — Input

Show `demo-subject/app.py` and `demo-subject/security-report.txt`. Point out
the self-owned Northstar Operations Diagnostics API, its health/job endpoints,
and the reported diagnostics route `/api/v1/diagnostics/resolve` with parameter
`host`. Do not show the env file or any key.

## 0:45–1:25 — Live dynamic investigation

Run the Docker-backed version for the video:

```bash
demo/run-docker-demo.sh
```

The script starts the API, Postgres ledger, and worker, queues the source via
the API, and lets the worker create the Celesto guest. The direct CLI command
remains available as a faster fallback if Docker is unavailable.

Show the model-driven sequence in `logs/commands.jsonl` or the terminal:

```text
list_source -> inspect_source -> send_request -> submit_finding
```

Mention that the model discovered the Northstar route and `host`; they were not
fixture allowlist values.

## 1:25–1:55 — Proof and independent recheck

Show the JSON report generated under `reports/investigations/` and highlight:

```text
verdict: verified
marker_detected: true
request_constructed_by: control_plane
independent_recheck.marker_detected: true
```

Explain that the first request is model-selected, while the fresh-token
independent request is constructed and checked by the trusted controller.

## 1:55–2:20 — Containment and cleanup

Show the containment report or prior live evidence. Say:

> There is no raw shell tool or arbitrary destination. The guest is network
> isolated, and the finalizer deletes it on success, failure, or interruption.

Show:

```bash
celesto computer list --cloud --json
```

and the empty computer list.

## 2:20–2:50 — Result and limitations

Show the Markdown report. State:

> The result is a bounded reproduction under supplied conditions, with source
> hash, request evidence, independent recheck, remediation, and cleanup state.
> Existing reliability, containment, and recovery artifacts are included in
> `reports/`. The retained patched counterpart uses the same business endpoint
> and produces `not_reproduced`.

Never show credentials, `.env`, raw API keys, or private source.
