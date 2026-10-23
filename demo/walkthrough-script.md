# Cairn submission walkthrough (target: 2:30–3:00)

## 0:00–0:20 — Problem and safety boundary

Show the repository README architecture diagram. Say:

> Cairn takes a security report and supplied source, runs the target only inside
> a fresh Celesto Cloud guest, and returns evidence-backed `verified`,
> `not_reproduced`, or `inconclusive`—never a universal safety claim.

## 0:20–0:45 — Input

Show `real-test-subject/app.py` and `security-report.txt`. Point out the
non-fixture route `/lookup` and parameter `q`. Do not show `.env` or any key.

## 0:45–1:25 — Live dynamic investigation

Run or show the recorded command:

```bash
python3 scripts/investigate.py \
  --source real-test-subject \
  --report-file real-test-subject/security-report.txt \
  --runtime python \
  --start-argv python3 app.py \
  --port 5002 \
  --investigation-id inv-real-dynamic-vercel-free-20261024
```

Show the model-driven sequence in `logs/commands.jsonl` or the terminal:

```text
list_source -> inspect_source -> send_request -> submit_finding
```

Mention that the model discovered `/lookup` and `q`; they were not fixture
allowlist values.

## 1:25–1:55 — Proof and independent recheck

Show the JSON report and highlight:

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
> `reports/`.

Never show credentials, `.env`, raw API keys, or private source.
