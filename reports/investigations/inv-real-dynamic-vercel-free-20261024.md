# Cairn investigation `inv-real-dynamic-vercel-free-20261024`

**Verdict:** `verified`

The reported behavior was reproduced and confirmed by an independent control-plane recheck.

## Claim

The GET /lookup endpoint appears vulnerable to OS command injection through the
q query parameter. An attacker-controlled q value may be concatenated into a
shell command. Please verify whether the claim is reproducible and distinguish
a real reproduction from a failed test setup.


## Evidence

- Source hash: `cc9d7b04afc3e8de260bc6294d5fffb747769457669a33a875e5c87c943e63a7`
- Route: `/lookup`
- Parameter: `q`
- Attempts: `4`
- Independent recheck: `confirmed`
- Agent evidence rationale: The /lookup endpoint runs `subprocess.run` with `shell=True` and directly interpolates the `q` query parameter into a shell command (`printf 'lookup %s' {name}`). Supplying `;id` as the `q` value caused the shell to execute `id`, confirming OS command injection. The test reproduced the injection reliably.

## Why

- At least one investigation request produced marker evidence.
- The control plane constructed a fresh independent request and observed its marker.

## Remediation

- Review the source location identified in the evidence.
- Replace shell composition with an argument vector or a safe library API.
- Validate attacker-controlled input before invoking operating-system functionality.

## Next action

Open a remediation ticket with the source hash and reproduction recipe.

## Dependencies

- Mode: `offline`
- Installation events: `1`

## Cleanup

- Sandbox deleted: `True`
