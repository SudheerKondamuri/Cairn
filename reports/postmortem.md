# Cairn evaluation post-mortem

## Measured result

The required matrix ran on 20 fresh, uniquely named Celesto Cloud guests.
Infrastructure success was 18/20, or **0.900**. The median wall-clock time was
68.634 seconds, p90 was 82.226 seconds, median boot-to-ready time was 9.131
seconds, and the recorded runtime total was $0.005299. These numbers are
recomputed from `reports/reliability.json`; failed rows were not removed.

## Verdict quality

The confusion matrix was **TP=9, FP=0, FN=1, TN=10**. The zero false-positive
result on patched fixtures is the most important safety outcome. The one false
negative was a vulnerable case whose Cloud guest creation returned HTTP 503
before the investigation could start; it is therefore an infrastructure
failure and not evidence that the fixture was patched.

## Failure analysis

The two unsuccessful infrastructure rows were `a-p-accurate` and
`b-v-stale`. Both failed during Celesto Cloud computer creation with HTTP 503
and both were cleaned up. The remaining 18 rows completed through the bounded
agent flow and final cleanup. The free NVIDIA NIM endpoint was sometimes slow
or returned no actionable tool call; Cairn therefore used the explicitly
recorded controller fallback after the controller had already inspected the
fixture source. The fallback makes one allowlisted marker request and still
requires the independent control-plane recheck for `verified`. This tradeoff
keeps the run bounded without pretending that model prose is evidence.

The live containment test blocked the prompt-injection exfiltration attempt,
confirmed loopback availability and external egress blocking, and verified the
host sentinel was unchanged. The live step-7 demonstration terminated the
fixture process, resumed the same persistent guest, restarted the fixture, and
recorded `policy_applied` with policy `resume`.
