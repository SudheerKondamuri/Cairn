# Cairn

Autonomous command-injection reproduction agent running inside Celesto
microVMs. A cairn is a marker left behind as proof that a path was actually
checked; Cairn applies that idea to AppSec triage.

> **Live-status note:** this repository contains measured Celesto Cloud evidence
> for Gate 0, containment, step-7 recovery, and the required 20-run evaluation.
> The recorded artifacts are retained under `reports/` and `reports/live/`.
> A fresh checkout still requires real provider keys in a local env file outside
> the checkout before rerunning any live command; no synthetic timings, costs, or
> containment results are presented as live evidence.

---

## Unified Full-Stack Application

Cairn runs as a single, cohesive full-stack product via Docker Compose. The Next.js web application, Flask control-plane API, PostgreSQL run ledger, and background Celesto worker operate as an integrated platform without fragmented manual setup.

```text
                                  Browser / Operator
                                          |
                                          | http://localhost:3000
                                          v
      +-----------------------------------------------------------------------+
      |  cairn-web (Next.js 16 / React 19)                                    |
      |  * Public Evidence Room: Northstar Vulnerable vs Patched walkthrough  |
      |  * Operator Workspace: Source upload, GitHub repo import, live traces |
      |  * Authentication: Local zero-friction mode or Hosted OAuth           |
      +-----------------------------------+-----------------------------------+
                                          |
                                          | http://api:8080 (internal proxy)
                                          v
      +-----------------------------------------------------------------------+
      |  cairn-api (Flask / Gunicorn Control Plane)                           |
      |  * Session validator, rate-limiting guard, and admission allowances   |
      |  * Multipart upload handler & GitHub archive validator               |
      |  * Investigation state machine & run queue                            |
      +-----------------+-----------------------------------+-----------------+
                        |                                   |
                        v                                   v
      +-----------------------------------+   +-------------------------------+
      |  cairn-ledger (PostgreSQL 16)     |   |  cairn-worker (Celesto SDK)   |
      |  * ACID run history               |   |  * Pulls queued investigations|
      |  * Multi-tenant accounts          |   |  * Boots isolated microVMs    |
      |  * Seeded initial run records     |   |  * Runs tool loop & rechecks  |
      +-----------------------------------+   +---------------+---------------+
                                                              |
                                                              | Celesto Cloud API
                                                              v
                                              +-------------------------------+
                                              |  Celesto Firecracker MicroVM  |
                                              |  * Outbound networking: OFF   |
                                              |  * Bounded guest tools        |
                                              |  * Independent marker oracle  |
                                              +-------------------------------+
```

---

## Quickstart: Run Everything in One Command

Run the entire stack (Postgres Ledger, Flask API, and Next.js Web UI) with Docker Compose:

```bash
docker compose up --build -d
```

Once started, verify the services and open the application:

| Component | URL / Endpoint | Purpose |
| --- | --- | --- |
| **Web Application** | `http://localhost:3000` | Full UI: Landing page, public evidence room, and `/operator` workspace |
| **API Health** | `http://localhost:8080/health` | Process liveness check (`{"status":"ok"}`) |
| **API Ready** | `http://localhost:8080/ready` | Database readiness check (`{"status":"ready"}`) |
| **Ledger Runs** | `http://localhost:8080/api/runs` | Seeded and executed run history |

### Local Mode (Default)
Out of the box, `CAIRN_ACCESS_MODE` defaults to `local`. Visiting `http://localhost:3000` gives you instant access to the **Open workspace** desk as `acct-local` with zero configuration—no OAuth credentials or API keys needed for evaluation.

### Hosted Multi-Tenant Mode
For public deployments, set `CAIRN_ACCESS_MODE=hosted` in your environment and provide OAuth credentials (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`). In hosted mode, users sign in with their identity provider, receive trial allowances (3 lifetime runs per user), and administrators can be designated via `CAIRN_ADMIN_IDENTITIES`.

### Running the Live Celesto Worker
To process queued investigations on real Celesto Cloud microVMs:

```bash
docker compose --profile worker up --build -d
```

The worker connects to PostgreSQL, picks up queued jobs, and orchestrates live Firecracker microVMs using the configured Celesto and LLM credentials.

---

## Problem Statement

AppSec engineers and security teams frequently receive free-text reports claiming that an application executes attacker-controlled operating-system commands (CWE-78). Before opening an engineering ticket, they need to know:
1. Whether the claim is real;
2. Whether the reporter tested the wrong route or parameter; and
3. Whether a failed reproduction attempt means the code is "patched" or merely that the test environment was misconfigured.

Cairn accepts a report and the subject source code or package, investigates strictly within the CWE-78 command-injection class inside an isolated Celesto microVM, and outputs `verified`, `not_reproduced`, or `inconclusive` alongside a structured request recipe, source hash, independent marker check, and attempt trace.

The repository includes two intentionally tiny test patterns with vulnerable and patched variants:

| Pattern | Route and input | Vulnerable behavior | Patched behavior |
| --- | --- | --- | --- |
| **A** | `/diagnose?host=...` | `shell=True` composition | validation + argument vector |
| **B** | `/convert?filename=...` | `os.system` composition | validation + `shutil.copy` |

The fixtures use Python's standard library HTTP server so they run cleanly in an air-gapped guest with outbound networking disabled.

---

## Live Demo Subject

The walkthrough and recorded evidence use `demo-subject/`, a self-owned Northstar Operations Diagnostics API:
- **Realistic Service Context**: Contains health, recent-job, and operator diagnostics endpoints (`GET /api/v1/diagnostics/resolve?host=...`).
- **`demo-subject/` (Vulnerable)**: Implements diagnostics with unsanitized shell execution, returning `verified` when Cairn triggers proof-of-execution tokens.
- **`demo-subject-patched/` (Patched)**: Implements argv-based subprocess execution with `shell=False`, returning `not_reproduced` after thorough fuzzing.

Both recorded cases are available for interactive inspection in the public evidence room at `http://localhost:3000/#investigation`.

---

## Why Celesto MicroVMs Are Essential

Testing untrusted security reports and exploit payloads in standard Docker containers or via host `subprocess.run()` is unsafe:
1. **Host & Container Escape Risk**: Exploit strings could execute on the host or attack the local network.
2. **Pollution & State Bleed**: Repeated exploit attempts corrupt the host filesystem, process tree, and environment variables.

Celesto provides microVM sandboxes with hardware-level boundary isolation:

### 1. Air-Gapped Network Policy
Each live guest is configured with an outbound network policy of `off` before boot. The subject application, HTTP probes, and marker verification oracle operate exclusively over the loopback interface (`127.0.0.1`). If the Celesto SDK cannot enforce network containment, Cairn fails closed rather than booting an open guest.

### 2. State-Preserving Step-7 Recovery
Under transient network or execution faults (such as mid-flight request failure at step 7), Cairn applies a `resume` policy:
- Stops and restarts the *same persistent guest*;
- Verifies workspace integrity and source hashes;
- Flushes marker directories; and
- Retries the probe with a fresh cryptographic token.
This preserves expensive dependency setup without entering an unbounded retry loop. Every path ends with an explicit deletion.

### 3. Independent Verification Oracle
The AI agent proposes when it believes an injection occurred, but **the agent never writes the final verdict**. Upon receiving a proposal, the trusted control plane issues an independent request using a fresh cryptographic marker token unknown to the model. Disagreements automatically downgrade the verdict to `inconclusive`.

---

## Control-Plane API Reference

The Flask control plane serves both automated grading scripts and web client proxying:

```text
GET  /health
  -> 200 {"status":"ok"}

GET  /ready
  -> 200 {"status":"ready"} when PostgreSQL is reachable;
     503 {"status":"not_ready", ...} otherwise

GET  /api/runs
  -> 200 JSON array of seeded and executed runs

POST /api/runs
  -> 201 with run_id, sandbox_name, problem_id, state, execution_target=celesto_sandbox

POST /api/investigations (multipart form: source archive, report, manifest)
  -> 202 with investigation_id and status=queued

GET  /api/investigations
  -> 200 Paginated investigation history with status filters

GET  /api/investigations/<id>
  -> 200 Status (queued/running/completed/failed) and full structured evidence report
```

---

## Evaluation Evidence & Measured Results

The evaluation matrix (`cases/evaluation_matrix.json`) tests two patterns across vulnerable and patched variants, subjected to 5 distinct report-quality challenges (20 total runs).

### Retained Evidence Files
- **Gate 0 Network Probe**: `reports/evidence/network_policy_probe.log` (verifies loopback success and external egress block)
- **Containment Test**: `reports/containment.json` (verifies prompt injection cannot escape the bounded tool loop or perform external curl)
- **Step-7 Failure Recovery**: `reports/failure_policy.json` and `reports/failure_trace.jsonl`
- **20-Run Evaluation Matrix**: `reports/reliability.json` and `reports/postmortem.md`

### Measured Metrics
- **Infrastructure Reliability**: 18/20 successes (90.0%)
- **Wall-clock Duration**: Median 68.6s, p90 82.2s
- **Boot-to-Ready Time**: Median 9.1s
- **Runtime Cost**: Total $0.005299 ($0.015/hr Celesto rate)
- **Confusion Matrix**: TP=9, FP=0, FN=1, TN=10 (The single false negative was caused by a transient Celesto Cloud HTTP 503 during guest creation, not an incorrect verdict).

---

## Verification & Testing

Verify that all local tests and live evaluation contracts pass:

```bash
# 1. Run unit and integration tests (59 passed)
PYTHONPATH=. .venv/bin/pytest tests/

# 2. Validate retained submission reports against the hackathon contract
python scripts/validate_reports.py --live
```

---

## Live Celesto Cloud Workflow

To run live investigations against Celesto Cloud from the CLI:

```bash
# Set your environment file containing CELESTO_API_KEY and LLM credentials
export CAIRN_ENV_FILE=/var/tmp/cairn.env

# Execute validation gates in order
python3 scripts/gate0.py
python3 scripts/run_one.py a-v-stale
python3 scripts/run_containment.py
python3 scripts/run_step7_failure.py
python3 scripts/run_evals.py
python3 scripts/validate_reports.py --live
```

---

## Repository Map

```text
frontend/            Next.js 16 Web UI: Landing page, evidence explorer, and /operator workspace
api/                 Flask REST control plane, rate-limiting security guards, and PostgreSQL repository
core/                Bounded agent loop, tool schemas, Celesto microVM adapter, and report generator
guest/               Fixed containment helpers mounted into the Celesto guest
fixtures/            Intentional standard-library vulnerable and patched test applications
demo-subject/        Northstar Operations Diagnostics API (vulnerable comparison)
demo-subject-patched/ Northstar Operations Diagnostics API (patched remediation)
migrations/          PostgreSQL ledger schema definitions
seeds/               Initial database seeds for runs and trial accounts
cases/               The 20-case evaluation matrix specification
reports/             Challenge-format evidence, audit logs, and generated investigation post-mortems
scripts/             Worker daemon, evaluation runners, Gate 0 probe, and validation tools
```

---

## Responsible Disclosure & Use

The vulnerable fixtures and Northstar demo subjects are intentionally insecure and must stay disposable and isolated within the Celesto microVM. Cairn is strictly intended for testing authorized source code and verifying reported claims on self-owned systems.
