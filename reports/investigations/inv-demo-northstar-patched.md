# Cairn investigation `inv-demo-northstar-patched`

**Verdict:** `not_reproduced`

The supplied security claim was not reproduced under the supplied runtime and test conditions.

## Claim

Security verification report
============================

Title: OS command injection in the Northstar Operations Diagnostics API

Application: Northstar Operations Diagnostics API
Version under review: 1.4.3
Affected component: operator diagnostics

The same report is retained for the patched comparison case. Verify whether
GET /api/v1/diagnostics/resolve?host=<value> still permits command injection.
The test must distinguish a patched implementation from an unavailable service
or an incorrectly constructed request, and should record the evidence used for
the conclusion.


## Evidence

- Source hash: `2a226e4bf5cfe82b89489dc406e0ea9113389d2b7ab4642ccd99ac5a40f87769`
- Route: `/api/v1/diagnostics/resolve`
- Parameter: `host`
- Attempts: `4`
- Independent recheck: `not requested`
- Agent evidence rationale: The controller finalized not_reproduced after the bounded agent budget was exhausted. Every recorded investigation attempt completed without control-plane marker evidence; no infrastructure or dependency failure was observed.

## Why

- The investigation completed without marker evidence (last HTTP status: 200).
- This result does not prove that every code path or configuration is safe.

## Remediation

- Review the tested path, parameter, source revision, and dependency versions.

## Next action

Confirm the application version and expand the harness if the report covers another path.

## Dependencies

- Mode: `offline`
- Installation events: `1`

## Cleanup

- Sandbox deleted: `True`
