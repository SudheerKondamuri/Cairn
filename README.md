# Cairn

Autonomous command-injection reproduction agent running inside Celesto
microVMs. A cairn is a marker left behind as proof that a path was actually
checked; Cairn applies that idea to AppSec triage.

> **Live-status note:** this checkout contains measured Celesto Cloud evidence
> for Gate 0, containment, step-7 recovery, and the required 20-run evaluation.
> The recorded artifacts are retained under `reports/` and `reports/live/`.
> A fresh checkout still requires real provider keys in a local env file outside
> the checkout before rerunning any live command; no synthetic timings, costs, or
> containment results are presented as live evidence.

## Problem statement

AppSec engineers and small teams receive free-text reports claiming that an
application executes attacker-controlled operating-system commands. Before
opening an engineering ticket, they need to know whether the claim is real,
whether the report used the wrong route or parameter, and whether a failed
attempt means “patched” or merely “the test environment broke.” Cairn accepts a
 report and the supplied subject source or package, investigates only the CWE-78
command-injection class, and returns `verified`, `not_reproduced`, or
`inconclusive` with a request recipe, source hash, independent marker check,
and attempt trace.

The repository contains two intentionally tiny patterns, each with vulnerable
and patched variants:

| Pattern | Route and input | Vulnerable behavior | Patched behavior |
| --- | --- | --- | --- |
| A | `/diagnose?host=...` | `shell=True` composition | validation + argument vector |
| B | `/convert?filename=...` | `os.system` composition | validation + `shutil.copy` |

The fixtures use Python's standard library HTTP server so they can run in a
guest with outbound networking disabled. They are test fixtures, not targets
to expose on a public network.

## Architecture

```text
                          untrusted report + subject source
                                      |
                                      v
        TRUSTED CONTROL PLANE (Docker Compose / Python process)
  +----------------------------------------------------------------+
  | bounded LLM tool loop | tool validator | marker oracle         |
  | independent recheck   | lifecycle/recovery | audit JSONL       |
  | Postgres run ledger    | final report writer                  |
  +-------------------------------+--------------------------------+
                                  |
                                  | Celesto SDK: create/start/exec/stop/delete
                                  v
        UNTRUSTED EXECUTION ZONE (one fresh Celesto Cloud computer)
  +----------------------------------------------------------------+
   | /input/source/*            user subject or package harness       |
  | /opt/cairn fixed helpers    /tmp/cairn-markers proof directory   |
  | no host mount               outbound network policy: off         |
  +----------------------------------------------------------------+
```

The model can choose only the bounded structured tools enabled for the
investigation: source inspection, local requests or a declared harness,
dependency installation, and finding submission. It cannot receive a raw shell
tool, arbitrary URL, host path, database connection, VM lifecycle operation, or
credential. The control plane constructs the independent recheck after the
model proposes `verified`; the model does not write the final verdict.

## Live demo subject

The video uses `demo-subject/`, a self-owned Northstar Operations Diagnostics
API. It is intentionally small and dependency-free, but has realistic internal
service context: health, recent-job, and operator diagnostics endpoints. The
accompanying report is written like an AppSec ticket and asks Cairn to verify an
OS command-injection claim against `GET /api/v1/diagnostics/resolve?host=...`.

`demo-subject-patched/` keeps the same routes and report context while using an
argv-based subprocess call with `shell=False`. The two live reports show the
intended contrast: `verified` for the vulnerable subject and
`not_reproduced` for the reachable patched subject. Both applications contain
synthetic data only and must remain inside the disposable sandbox.

## How I used Celesto

### Network policy

Each live guest is configured with an outbound network policy of `off` before
it starts. The fixture, HTTP probe, and marker oracle use only loopback. The
runner fails closed if the installed SDK cannot represent the policy rather
than silently creating an open guest. Gate 0 records that loopback works and
an external probe fails. The installed SDK version exposes the cloud request
field through its generated model while its public `Computer` CloudOptions do
not yet expose it, so `scripts/runner.py` validates and sets that model field
before creation.

### Persistence

The step-7 failure policy is `resume`: the same persistent Celesto computer is
stopped and started again, its source/workspace is checked, the marker
directory is cleared, and the request is retried with a fresh token. This
preserves known-good setup while avoiding an unbounded retry loop. Every path,
including interruption, ends with explicit deletion.

Recorded evidence is retained in:

- `reports/evidence/network_policy_probe.log`
- `reports/evidence/persistence_probe.log`
- `reports/failure_trace.jsonl`
- `scripts/gate0.py`
- `scripts/run_step7_failure.py`

### Why Celesto is necessary

Replacing Celesto with `subprocess.run()` would execute the deliberately
vulnerable fixture and the exploit payload in the control-plane environment.
The microVM gives the investigation a separate filesystem, process namespace,
network policy, lifecycle, and persistent workspace. The API and Postgres
ledger queue and record investigation jobs; the worker and live scripts boot
Celesto guests.

## Control-plane API

The default Compose stack contains two services:

- `api` on port `8080`
- `ledger` on PostgreSQL

An optional `worker` profile is included for a reproducible queue deployment.
Start it with `docker compose --env-file /var/tmp/cairn.env --profile worker up --build -d`; it shares the
ledger and upload/report volumes with the API. The worker image pins the
installed Celesto SDK version. Docker build verification must be performed on a
Docker-enabled host.

Celesto guests are created by the live scripts through the SDK, not as a
Compose service.

```text
GET  /health
  -> 200 {"status":"ok"}

GET  /ready
  -> 200 {"status":"ready"} when Postgres is reachable;
     503 {"status":"not_ready", ...} otherwise

GET  /api/runs
  -> JSON array, seeded with sbx-seeddemo1

POST /api/runs
  -> 201 with run_id, sandbox_name, problem_id, state,
         execution_target=celesto_sandbox

POST /api/investigations (multipart form)
  -> 202 with investigation_id and status=queued
     fields: source (tar archive), report, manifest (JSON)

GET  /api/investigations/<investigation_id>
  -> queued, running, completed, or failed status plus the detailed result
```

For a public deployment, set `CAIRN_API_KEY` and keep
`CAIRN_REQUIRE_API_AUTH=true`. Sensitive `/api/*` routes accept either
`X-Cairn-API-Key: <key>` or `Authorization: Bearer <key>`. The API also applies
a bounded per-client in-process rate limit; use a shared gateway/rate limiter
when running multiple API replicas.

The POST endpoint rejects host execution targets, unknown states, and sandbox
names that do not match `sbx-` plus at least eight lowercase letters/digits.

`/api/investigations` queues a user-supplied source archive. Run
`python3 scripts/worker.py` on a machine with the Celesto and LLM credentials to
process queued jobs. Source archives are deleted by the worker after completion
or failure; the JSON and Markdown reports remain under
`reports/investigations/`.

The first investigation MVP supports two subject types:

```json
{
  "subject_type": "http_app",
  "runtime": "python",
  "start_argv": ["python3", "app.py"],
  "port": 5000,
  "working_directory": ".",
  "dependency_mode": "offline"
}
```

or:

```json
{
  "subject_type": "package_harness",
  "runtime": "node",
  "test_argv": ["node", "cairn-harness.js"],
  "working_directory": ".",
  "dependency_mode": "offline"
}
```

Package harnesses signal a reproduced behavior by creating the marker named by
the `CAIRN_MARKER_TOKEN` environment variable. The control plane runs the
harness again with a fresh token before accepting `verified`.

## Agent and proof flow

1. Create a unique fresh guest with network policy set before boot.
2. Upload the source and fixed guest helpers; compute/verify the source hash.
3. Install approved dependencies, then start the subject or declared harness and
   initialize an empty marker directory.
4. Give the model the report as untrusted data and only the schemas enabled for
   this investigation: source inspection, local requests or a declared
   harness, dependency installation, and finding submission.
5. After every request, the control plane checks the marker directory and gives
   the model only `marker_detected: true/false`.
6. A `verified` proposal triggers a fresh control-plane-created token and an
   independent request/check. A disagreement becomes `inconclusive`.
7. Stop and delete the guest in a `finally` path.

Model-controlled values are URL-safe base64 encoded before reaching a fixed
guest helper command. Thus a string such as `; touch ...` is an HTTP payload
for the vulnerable fixture, not a second control-plane shell command.

## State and failure design

The designed failure is step 7 of 10: the first request dispatch fails after
the app may or may not have received it. The outcome is recorded as unknown;
it is never treated as marker absence. The `resume` policy then:

1. records `step_failed` at step 7;
2. stops and starts the same persistent guest;
3. verifies the source/workspace and restarts the fixture;
4. clears markers and retries with a new token;
5. escalates to a fresh guest if recovery itself cannot restore health; and
6. deletes all guests in the finalizer.

The policy and trace are stored in `reports/failure_policy.json` and
`reports/failure_trace.jsonl`. Run `python3 scripts/run_step7_failure.py` for
the same state machine with an in-memory adapter.

## Containment test

The containment attack is a prompt-injected report that tells the agent to
ignore the investigation and run an external `curl` command. The primary
defense is the strict tool surface: there is no `run_shell` tool and no
arbitrary destination field. Defense in depth is the Celesto network policy,
which is checked by a guest-local loopback plus external-egress probe.

Run:

```bash
python3 scripts/run_containment.py
```

This writes `reports/containment.json`,
`reports/evidence/containment_tool_schema.log`, and
`reports/evidence/containment_network_probe.log`. The current live artifact
records `blocked: true` and `host_untouched: true`; on a fresh checkout, rerun
the command before treating the checked-in evidence as current.

## Eval report

The required matrix is `cases/evaluation_matrix.json`: two patterns, vulnerable
and patched variants, and five report-quality variants each. Each run creates a
new sandbox name and records:

- infrastructure success (`created -> ready -> running -> final -> deleted`);
- verdict and ground truth separately;
- wall-clock duration;
- boot-to-ready duration; and
- estimated runtime cost using `CELESTO_COST_PER_HOUR` (default `$0.015/hr`).

Run a one-case smoke check:

```bash
python3 scripts/run_one.py a-v-stale
```

Run all 20 fresh guests:

```bash
python3 scripts/run_evals.py
```

The script writes `reports/reliability.json` and a measured
`reports/postmortem.md`. It retains failed rows and reports a confusion matrix
(`TP`, `FP`, `FN`, `TN`) separately from infrastructure reliability. Do not
replace pending artifacts with hand-written numbers.

The measured run currently reports 18/20 infrastructure successes (0.900),
median wall-clock time 68.634 seconds, p90 82.226 seconds, median boot-to-ready
9.131 seconds, total recorded runtime cost $0.005299, and verdict matrix
TP=9, FP=0, FN=1, TN=10. The one vulnerable false negative was a Celesto Cloud
HTTP 503 during guest creation; it was not a patched verdict.

The optional stretch run attempts five overlapping uniquely named guests:

```bash
python3 scripts/run_concurrency.py
```

It records observed rate limits, credits, transport failures, and cleanup
outcomes in `reports/concurrency.json`.

The observed stretch run attempted five overlapping guests and completed 1/5;
the other four were rejected by the free-trial one-sandbox limit with HTTP 429.
That limitation is recorded as evidence rather than hidden.

## Setup

### Offline control-plane tests (available now)

Python 3.11+ is required. From the repository root:

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
```

The current tests cover strict tool validation, encoded guest arguments,
marker/recheck behavior, step-7 recovery, fixture contrasts, API validation,
reliability arithmetic, dynamic source bundles, dynamic routes, dependency
installation policy, package harnesses, and detailed investigation reports.

### Dynamic investigation from the CLI

The evaluation matrix is not required for a user investigation. Supply a source
directory or tar archive, a report, and a structured start argv:

```bash
python3 scripts/investigate.py \
  --source ./my-app \
  --report-file ./security-report.txt \
  --runtime python \
  --start-argv python3 app.py \
  --port 5000
```

The command writes:

```text
reports/investigations/<investigation_id>.json
reports/investigations/<investigation_id>.md
```

For a public GitHub repository, Cairn can fetch a tagged, branched, or commit
archive in the trusted control plane before applying the same source validation.
The guest does not receive the URL and does not need outbound networking:

```bash
python3 scripts/investigate.py \
  --github-url https://github.com/OWNER/REPOSITORY \
  --github-ref main \
  --report-file ./security-report.txt \
  --runtime python \
  --start-argv python3 app.py \
  --port 5000
```

GitHub acquisition is CLI-only in this MVP; the multipart API continues to
accept validated source archives. Use a small repository and an explicit
runtime argv rather than running repository setup scripts on the host.

If a dynamic investigation exhausts its bounded agent budget after complete,
marker-free attempts, the trusted controller may finalize `not_reproduced` from
those observations. Unknown request outcomes, dependency failures, or any
positive marker remain `inconclusive` unless the normal finding submission and
independent recheck complete.

The application is launched inside Celesto without a shell. The AI can inspect
arbitrary files, identify a route and parameter, request an approved dependency
installation, and submit a finding. If the subject is a package, use a harness:

```bash
python3 scripts/investigate.py \
  --source ./package-with-harness \
  --report "The merge function may allow prototype pollution." \
  --subject-type package_harness \
  --runtime node \
  --test-argv node cairn-harness.js
```

The harness should create the file
`/tmp/cairn-markers/$CAIRN_MARKER_TOKEN` when it reproduces the reported
behavior. Cairn runs it again with a fresh token before accepting `verified`.

Dependency installation is offline by default. Python `requirements.txt` and
Node `package.json`/`package-lock.json` are supported by the guest installer
when the required packages are already available in the guest cache or bundle.
Controlled registry access remains an explicit provider-dependent mode and must
not be assumed to be available when outbound networking is disabled.

### Queued API investigation

Start the Compose ledger/API, then submit a tar archive as multipart form data:

```bash
curl -F source=@my-app.tar.gz \
  -F report='The upload filename may execute commands.' \
  -F 'manifest={"subject_type":"http_app","runtime":"python","start_argv":["python3","app.py"],"port":5000}' \
  http://localhost:8080/api/investigations
```

Run the worker from a machine with the Celesto and LLM credentials. Because the
worker runs outside the Compose network, override the database hostname with
`127.0.0.1`:

```bash
DATABASE_URL=postgresql://ledger:replace-me@127.0.0.1:5432/ledger \
  python3 scripts/worker.py
```

For the optional Compose worker instead:

```bash
docker compose --env-file /var/tmp/cairn.env --profile worker up --build -d
```

Then retrieve the status and detailed report using the returned
`investigation_id`:

```bash
curl http://localhost:8080/api/investigations/<investigation_id>
```

### Docker Compose ledger

Install Docker Desktop or Docker Engine with Compose, then run:

```bash
cp .env.example /var/tmp/cairn.env
# These two values must use the same password.
# POSTGRES_PASSWORD=replace-me
# DATABASE_URL=postgresql://ledger:replace-me@ledger:5432/ledger
docker compose --env-file /var/tmp/cairn.env up --build -d
curl http://localhost:8080/health
curl http://localhost:8080/ready
curl http://localhost:8080/api/runs
```

The first database boot loads `seeds/01_runs.sql`; no manual migration is
needed. The ledger is intentionally kept on the private Compose network rather
than published on a host port; the API and worker reach it as `ledger:5432`.
Keep the password in `DATABASE_URL` equal to `POSTGRES_PASSWORD` in the external env file; the
example uses `replace-me` consistently for the local demo. Docker is not
available in the current development container, so this check must be run on a
Docker-enabled machine.

If `/health` returns `{"status":"ok"}` but `/api/runs` returns `database
unavailable`, the API is alive but its Postgres credentials do not match. Fix
the two values in the external env file, then recreate the API. If the database was initialized
with a different password and this is only disposable demo data, reset the
volume before starting again:

```bash
docker compose --env-file /var/tmp/cairn.env down -v
docker compose --env-file /var/tmp/cairn.env up --build -d
curl http://localhost:8080/health
curl http://localhost:8080/ready
curl http://localhost:8080/api/runs
```

### Live Celesto Cloud run

Install the SDK and create an uncommitted local env file outside the repository:

```bash
python3 -m pip install celesto
cp .env.example /var/tmp/cairn.env
```

Set these local-only values in `/var/tmp/cairn.env`:

```text
CELESTO_PROVIDER=cloud
CELESTO_API_KEY=<your Celesto Cloud key>
CELESTO_BACKEND=firecracker
CELESTO_TEMPLATE_ID=coding-agent
LLM_BASE_URL=https://<your-openai-compatible-provider>/v1
LLM_API_KEY=<your LLM key>
LLM_MODEL=<your model name>
LLM_TIMEOUT_S=20
LLM_MAX_TOKENS=512
INVESTIGATION_TIMEOUT_S=150
DATABASE_URL=postgresql://ledger:<same-password-as-POSTGRES_PASSWORD>@ledger:5432/ledger
API_PORT=8080
```

Never commit the env file, provider keys, or real application credentials. Pass
the file explicitly to live commands; the repository root should contain no
`.env` file in the submission checkout. Then run the gates in order:

```bash
export CAIRN_ENV_FILE=/var/tmp/cairn.env
python3 scripts/gate0.py
python3 scripts/run_one.py a-v-stale
python3 scripts/run_containment.py
python3 scripts/run_step7_failure.py
python3 scripts/run_evals.py
python3 scripts/run_concurrency.py
python3 scripts/validate_reports.py --live
```

If Gate 0 fails, stop and fix the provider/image/network-policy issue before
spending credits on the 20-run matrix.

## Repository map

```text
api/                 Flask ledger API and Postgres repository
core/                dynamic investigation contract, tool boundary, agent loop, sandbox adapter, reports
fixtures/            four intentional standard-library target applications
guest/               fixed helpers copied into the Celesto guest
scripts/              dynamic CLI/worker, Gate 0, live runs, evals, containment, recovery
cases/               the 20-case evaluation matrix
demo-subject/        self-owned Northstar diagnostics API used in the video
demo-subject-patched/ patched counterpart for the negative comparison
reports/              challenge-format evidence and per-investigation reports
logs/                append-only Celesto command audit log
```

## Disclosure and responsible use

The vulnerable fixtures and the Northstar demo subject are intentionally
insecure and must stay disposable and local to the sandbox. Cairn is not a
permission to test applications that are not owned by the operator. The
implementation was developed with an AI coding assistant; all generated code
is reviewed through the tests and the explicit Celesto boundary.
