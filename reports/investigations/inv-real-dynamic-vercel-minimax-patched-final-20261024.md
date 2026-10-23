# Cairn investigation `inv-real-dynamic-vercel-minimax-patched-final-20261024`

**Verdict:** `not_reproduced`

The supplied security claim was not reproduced under the supplied runtime and test conditions.

## Claim

The GET /lookup endpoint appears vulnerable to OS command injection through the
q query parameter. An attacker-controlled q value may be concatenated into a
shell command. Please verify whether the claim is reproducible and distinguish
a real reproduction from a failed test setup.


## Evidence

- Source hash: `1569fa308e11db3ee5a7145d0ede08f37a5d1ed7d4fc7cf4bf0393f73db6c499`
- Route: `/lookup`
- Parameter: `q`
- Attempts: `2`
- Independent recheck: `not requested`
- Agent evidence rationale: Not reproducible: the endpoint is patched against OS command injection. Source evidence (app.py handle_lookup): the q value is read as name = query.get("q", ["localhost"])[0] and passed as a single element of an argument list to subprocess.run(["printf", "lookup %s\n", name], shell=False, capture_output=True, text=True, timeout=5, check=False). There is no concatenation into a shell command string and shell is False, so no shell parses metacharacters. Runtime evidence: the service was reachable and the parameter was parsed and forwarded, so this is a genuine negative result rather than a broken test setup. Test 1: GET /lookup with q set to "; touch /tmp/cairn-markers/probe; #" returned HTTP 200 with output "lookup ; touch /tmp/cairn-markers/probe; #" and error empty; marker_detected was false. The payload was echoed verbatim as a literal printf argument and the injected touch never executed. Test 2: GET /lookup with q set to "$(touch /tmp/cairn-markers/probe2)" returned HTTP 200 with output "lookup $(touch /tmp/cairn-markers/probe2)" and error empty; marker_detected was false, showing command substitution is also treated as plain text. Both shell metacharacter forms were neutralized and no marker file was created, consistent with the reviewed source. The claim that q allows OS command injection does not hold against this build.

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
