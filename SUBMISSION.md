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
| 20-case Celesto evaluation | 18/20 run completion; inspect verdict quality separately | `reports/reliability.json`, `reports/live/`, `reports/postmortem.md` |
| Prompt-injection containment | blocked; host untouched; external egress blocked | `reports/containment.json`, `reports/evidence/containment_network_probe.log` |
| Persistence/recovery | file survived stop/start | `reports/evidence/persistence_probe.log` |
| Network policy | loopback worked; external probe blocked | `reports/evidence/network_policy_probe.log` |
| Live production deployment | `active`; Next.js 16 Web UI, API, worker & PostgreSQL | `http://54.196.136.14` |

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
| Verdict quality | **Inspect retained per-case outcomes** | Setup failures have no verdict and must be distinguished from completed investigations with incorrect verdicts |
| Prompt-injection containment | **PASS from retained live evidence** | `reports/containment.json`; tool schema blocked, host untouched, external egress blocked |
| Step-7 persistence/recovery policy | **PASS** | `reports/failure_policy.json`, `reports/failure_trace.jsonl`, `reports/evidence/persistence_probe.log` |
| Cleanup on success/failure/interruption | **PASS** | `reports/lifecycle.json`; current Celesto Cloud list is empty |
| Dynamic user-supplied source/report flow | **PASS** | Vulnerable and patched non-fixture reports in `reports/investigations/` |
| GitHub repository source acquisition | **PASS** | CLI `--github-url` and Web UI repository importer; archives validated before guest upload |
| Detailed JSON and Markdown reports | **PASS** | Current dynamic reports plus all live fixture reports; downloadable via Web UI, API, and disk |
| API intake contract | **PASS — Verified in production** | FastAPI/Flask control plane contract tested in pytest; verified live with PostgreSQL ledger in Docker Compose |
| API authentication/readiness/rate limiting | **PASS** | Token authentication, ready/health probes, and rate-limiting middleware operational in production |
| Automated CI checks | **PASS — 62 tests passing** | `.github/workflows/ci.yml`; pytest suite (62 passed, 5 skipped) and compilation verified |
| Worker archive claim/extract/complete/delete mechanics | **PASS in smoke test** | Worker mechanics tested with and without LLM |
| Reproducible worker deployment | **PASS — Verified in production** | `Dockerfile.worker` fully operational in Docker Compose and on live AWS EC2 host with Celesto Cloud SDK |
| Full-stack web application & operator desk | **PASS — Deployed** | Next.js 16 / React 19 frontend with public evidence room, interactive investigation creator, and live audit ledger (`http://54.196.136.14`) |
| Dependency policy and package-harness contract | **PASS in tests** | `tests/test_dynamic_mvp.py`; clean boundary enforcement for untrusted repositories |
| Optional five-job concurrency stretch | **Attempted and documented** | `reports/concurrency.json`; 1/5 completed, four free-trial HTTP 429 responses |
| Public repository | **PUSHED — verify visibility** | `origin/main` contains the current commit; confirm the repository is public and paste its URL into the submission form |
| Demo video, three minutes or less | **Needs trimming: current recording is about 4:10** | `demo/walkthrough.mp4`; reproduce using Web UI or `demo/run-docker-demo.sh` |
| Upstream open-source contribution | **Submitted** | Feature request filed at [CelestoAI/celesto#708](https://github.com/CelestoAI/celesto/issues/708) |

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
reports for navigation. Keep all required evaluation failures and audit records;
supplementary recording retries can be archived outside the checkout.

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

## Upstream Celesto open-source contribution

During real-world evaluation across isolated Firecracker microVMs with untrusted subjects, an architectural feature request was identified, formally specified, and submitted to the upstream Celesto repository:

- **Upstream Issue**: [CelestoAI/celesto#708](https://github.com/CelestoAI/celesto/issues/708) — *Support atomic runtime transitions for outbound network policy*
- **Technical Context**: Celesto's `internet_settings` is currently configured at sandbox creation time and remains immutable across the microVM lifecycle. Untrusted security investigation workflows face a structural tension: dependency installation (e.g., `pip`, `npm`) requires outbound package registry access, but untrusted code execution and vulnerability probing require strict outbound egress denial to prevent reverse shells and prompt-injection token exfiltration.
- **Proposed Enhancement**: A host-enforced, atomic `update_network_policy()` transition method on the Celesto computer handle, allowing callers to safely shift from an open installation policy to a loopback/deny policy without tearing down and recreating the guest machine.

## Reproduce the strongest demo

Cairn supports three reproduction workflows depending on the reviewer's preferred environment:

### Option 1: Live Cloud Deployment (Zero Local Setup)

The full Cairn stack is running live on AWS EC2 with full Celesto Cloud microVM orchestration:

1. Navigate to the live operator interface: `http://54.196.136.14/operator/investigations/new`
2. Select the Northstar demo subject (`demo-subject`) or upload a custom repository archive/GitHub URL.
3. Input the security report from `demo-subject/security-report.txt`, set start command `python3 app.py`, and port `5002`.
4. Submit the investigation. The Celesto worker boots a Firecracker microVM, executes the bounded probe loop with independent verification, records all evidence into the PostgreSQL ledger, and generates exportable PDF, Markdown, and JSON reports in real time.
5. Contrast against the patched counterpart at `demo-subject-patched/` to observe the `not_reproduced` verdict.

### Option 2: Full-Stack Docker Compose (One-Command Local Reproduction)

Run the unified full stack (PostgreSQL run ledger, Flask REST control plane, Next.js 16 Web UI, and Celesto background worker) locally:

```bash
# Configure credentials in .env (CELESTO_API_KEY, LLM credentials)
docker compose --profile worker up --build -d
```

Once running:
- Web Application: `http://localhost:3000` (Access the Public Evidence Room and `/operator` workspace)
- API Health & Swagger: `http://localhost:8080/health` and `http://localhost:8080/ready`
- Automated Docker Demo Script:
  ```bash
  demo/run-docker-demo.sh
  ```
  This submits the Northstar source through the API. The worker creates the Celesto guest and writes the detailed report under `reports/investigations/`.

### Option 3: Headless CLI (Direct Runner)

To run a headless investigation without starting the web UI or database:

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
reports/investigations/inv-demo-northstar.json
reports/investigations/inv-demo-northstar.md
```

The committed walkthrough recording is `demo/walkthrough.mp4`; reproduction commands are in `demo/README.md`.

## Checks run for this checkout

```bash
PYTHONPATH=. .venv/bin/pytest -q
python3 -m compileall -q api core demo-subject demo-subject-patched fixtures guest scripts tests
python3 scripts/validate_reports.py --live
```

The expected current results are 62 tests passing (5 skipped), successful compilation, and
`VALID: Cairn submission reports ...`.

## Final manual submission steps

1. Check that `demo/walkthrough.mp4` is three minutes or less; trim or replace it if needed.
2. Confirm the pushed repository is public and that `.env`, keys, uploaded
   bundles, and private source are excluded.
3. Confirm GitHub Actions passes, then submit the repository URL, live deployment URL (`http://54.196.136.14`), video URL/file,
   and this evidence packet.

Do not show `.env`, API keys, or private source in the recording.
