# Cairn hackathon submission packet

## What Cairn demonstrates

Cairn accepts a security report and supplied source, launches the subject inside
a fresh Celesto Cloud microVM, gives an external LLM only bounded structured
tools, and returns an evidence-backed verdict:

- `verified` — marker evidence plus a controller-built independent recheck;
- `not_reproduced` — complete tested attempts without marker evidence;
- `inconclusive` — setup, dependency, transport, or evidence uncertainty.

The verdict is scoped to the supplied source, runtime, dependencies, and tested
conditions. It is not a universal safety claim.

## Current live evidence

| Evidence | Result | Artifact |
| --- | --- | --- |
| Northstar self-owned demo application | `verified` with independent recheck | `reports/investigations/inv-demo-20261024-055325.json` and `.md` |
| Northstar patched comparison | `not_reproduced`; service reachable and marker-free | `reports/investigations/inv-demo-northstar-patched.json` and `.md` |
| Non-fixture vulnerable dynamic app | `verified` | `reports/investigations/inv-real-dynamic-vercel-free-20261024.json` |
| Non-fixture patched dynamic app | `not_reproduced` | `reports/investigations/inv-real-dynamic-vercel-minimax-patched-final-20261024.json` |
| 20-case Celesto evaluation | 18/20 infrastructure success; TP=9, FP=0, FN=1, TN=10 | `reports/reliability.json`, `reports/postmortem.md` |
| Prompt-injection containment | blocked; host untouched; external egress blocked | `reports/containment.json`, `reports/evidence/containment_network_probe.log` |
| Persistence/recovery | file survived stop/start | `reports/evidence/persistence_probe.log` |
| Network policy | loopback worked; external probe blocked | `reports/evidence/network_policy_probe.log` |

The current dynamic reports were produced through the normal LLM tool loop;
they are not controller-only synthetic results. Celesto guest names are recorded
in the reports and the post-run cloud listing was empty.

## Complete requirement checklist

This is the repository's full documented gate list. The 20-case matrix is
already complete; it is not an item still waiting to be run.

| Requirement | Status | Evidence / note |
| --- | --- | --- |
| Gate 0: Celesto Cloud guest creation and network policy | **PASS** | `reports/evidence/network_policy_probe.log`; loopback worked and external egress was blocked |
| Gate 0: persistent workspace | **PASS** | `reports/evidence/persistence_probe.log`; file survived stop/start |
| One live vulnerable smoke case | **PASS** | `reports/live/a-v-accurate.json`; verified with independent recheck and cleanup |
| Required 20-case evaluation | **PASS — complete** | `reports/reliability.json`; exactly 20 fresh case reports under `reports/live/` |
| 20-case infrastructure reliability | **Measured, not perfect** | 18/20 = 0.900; two Cloud HTTP 503 creation failures were retained and cleaned up |
| 20-case confusion matrix | **PASS with recorded limitation** | TP=9, FP=0, FN=1, TN=10; the FN was the HTTP 503 infrastructure failure, not a patched verdict |
| Prompt-injection containment | **PASS from retained live evidence** | `reports/containment.json`; tool schema blocked, host untouched, external egress blocked |
| Step-7 persistence/recovery policy | **PASS** | `reports/failure_policy.json`, `reports/failure_trace.jsonl`, `reports/evidence/persistence_probe.log` |
| Cleanup on success/failure/interruption | **PASS** | `reports/lifecycle.json`; current Celesto Cloud list is empty |
| Dynamic user-supplied source/report flow | **PASS** | Vulnerable and patched non-fixture reports in `reports/investigations/` |
| GitHub repository source acquisition | **PASS in CLI** | `scripts/investigate.py --github-url ...`; archives are validated before guest upload |
| Detailed JSON and Markdown reports | **PASS** | Current dynamic reports plus all live fixture reports |
| API intake contract | **PASS in tests** | `tests/test_api.py`; actual Docker/Postgres run still needs a Docker-enabled host |
| API authentication/readiness/rate limiting | **PASS in tests** | Configure `CAIRN_API_KEY` and `CAIRN_REQUIRE_API_AUTH=true` before public exposure |
| Automated CI checks | **Workflow committed** | `.github/workflows/ci.yml`; confirm the post-push GitHub Actions result before submitting |
| Worker archive claim/extract/complete/delete mechanics | **PASS in smoke test** | Worker mechanics tested without LLM |
| Reproducible worker deployment | **Prepared, Docker build unverified here** | `Dockerfile.worker`; start with `docker compose --profile worker up --build -d` on a Docker-enabled host |
| Dependency policy and package-harness contract | **PASS in tests** | `tests/test_dynamic_mvp.py`; no real dependency-heavy repo was needed |
| Suspicious Package Detonator idea | **PARTIAL / not shipped** | Dependency install exists, but install telemetry, filesystem/process/network snapshots, and package risk scoring are not implemented |
| Optional five-job concurrency stretch | **Attempted and documented** | `reports/concurrency.json`; 1/5 completed, four free-trial HTTP 429 responses |
| Public repository | **PUSHED — verify visibility** | `origin/main` contains the current commit; confirm the repository is public and paste its URL into the submission form |
| Demo video, three minutes or less | **PENDING manual action** | `demo/walkthrough-script.md` and executable `demo/run-demo.sh` are ready; `demo/walkthrough.mp4` is still missing |

## GitHub submission hygiene

The public repository should contain the implementation, the exact grader-read
artifacts, the self-owned demo subject, and enough evidence for a reviewer to
understand the result. Keep the paths listed in the challenge contract,
`api/`, `core/`, `guest/`, the required evaluation `fixtures/`, the focused
`tests/`, the live/demo scripts, and the retained reports/evidence.

Never commit `.env` or any provider/LLM/API key. Also exclude `.cairn/`,
`__pycache__/`, `*.pyc`, local uploaded archives, temporary recordings, and
private source. If the video is uploaded separately, link it from this file or
the README instead of committing a large binary. Keep only final, real demo
reports rather than failed retry output created while recording.

### The 20-case test in detail

`cases/evaluation_matrix.json` contains 20 rows:

- Pattern A vulnerable: 5 report variants;
- Pattern A patched: 5 report variants;
- Pattern B vulnerable: 5 report variants;
- Pattern B patched: 5 report variants.

The variants cover accurate, wrong parameter, wrong route, vague, and stale
reports. Every row has a retained JSON artifact in `reports/live/`, a unique
Celesto sandbox name, infrastructure status, verdict, truth label, timing, and
cleanup result. Do **not** rerun the matrix unless code changes invalidate the
recorded evidence; it costs credits and does not improve the submission by
itself.

## Reproduce the strongest demo

Keep credentials in an uncommitted env file outside the repository and run:

```bash
export CAIRN_ENV_FILE=/var/tmp/cairn.env
python3 scripts/investigate.py \
  --source demo-subject \
  --report-file demo-subject/security-report.txt \
  --runtime python \
  --start-argv python3 app.py \
  --port 5002 \
  --investigation-id inv-demo-northstar
```

Then inspect:

```text
reports/investigations/inv-demo-vulnerable.json
reports/investigations/inv-demo-vulnerable.md
```

The patched counterpart is in `demo-subject-patched/`. The demo shot list and
narration are in `demo/walkthrough-script.md`.

The preferred Docker-backed recording command is:

```bash
demo/run-docker-demo.sh
```

It starts the trusted API, Postgres ledger, and worker, then submits the
Northstar source through the API. The worker creates the Celesto guest and
writes the detailed report under `reports/investigations/`.

## Checks run for this checkout

```bash
python3 -m pytest -q
python3 -m compileall -q api core demo-subject demo-subject-patched fixtures guest scripts tests
python3 scripts/validate_reports.py --live
```

The expected current results are 47 tests passing, successful compilation, and
`VALID: Cairn submission reports ...`.

## Final manual submission steps

1. Record `demo/walkthrough.mp4` (three minutes or less) using the shot list.
2. Confirm the pushed repository is public and that `.env`, keys, uploaded
   bundles, and private source are excluded.
3. Confirm GitHub Actions passes, then submit the repository URL, video URL/file,
   and this evidence packet.

Do not show `.env`, API keys, or private source in the recording.
