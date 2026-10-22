# Northstar Operations Diagnostics API

This is the self-owned application used for Cairn's live demonstration. It is
small, dependency-free, and representative of an internal operations service:
it exposes health, recent-job, and host-diagnostics endpoints.

The diagnostics implementation is intentionally unsafe for this controlled
security-verification exercise. It must only run inside a disposable Celesto
guest or as a local test process with synthetic input. It has no credentials,
customer data, or outbound network dependency.

The accompanying `security-report.txt` is written as an AppSec report rather
than as an exploit script. Cairn must inspect the source, discover the route and
parameter, send a bounded loopback request, and independently verify the
marker evidence before returning a verdict.
