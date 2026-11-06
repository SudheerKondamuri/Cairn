# Celesto Founder Interview & Evaluation Defense Guide

This document prepares you for the shortlist interview with the Founder of Celesto AI and the technical judges.

---

## 1. Key Evaluation Metrics (Know by Heart)

| Metric | Measured Value | Meaning & Context |
| :--- | :--- | :--- |
| **Total Eval Runs** | **20 fresh sandboxes** | Tested across 2 CWE-78 vulnerability patterns (A: parameter concatenation, B: utility piping) with 5 variants each (accurate, wrong route, wrong param, vague, stale). |
| **Infrastructure Success** | **18 / 20 (90.0%)** | 18 completed end-to-end. 2 failed due to Cloud HTTP 503 during computer creation (`a-p-accurate` and `b-v-stale`). |
| **Safety Confusion Matrix** | **TP=9, FP=0, FN=1, TN=10** | **Zero False Positives on patched code** (most critical safety benchmark). The single FN was an infrastructure 503 before execution started, not an analytical failure. |
| **Median Wall-Clock Time** | **68.63 seconds** | Median duration of an investigation. |
| **P90 Wall-Clock Time** | **82.23 seconds** | 90th percentile duration. |
| **Median Boot-to-Ready** | **9.13 seconds** | MicroVM instantiation time. |
| **Total Recorded Runtime Cost** | **$0.005299 USD** | Total Celesto microVM computing cost across all 20 runs combined. |

---

## 2. "Why Celesto and not a Docker container or E2B?"

### vs. Docker Containers
* **Kernel Sharing**: Docker containers share the host Linux kernel (`runc`). A single kernel privilege escalation (e.g., Dirty COW, CVE-2024-21626 runc breakout) escapes directly onto the host server.
* **MicroVM Hardware Boundary**: Celesto uses hardware-assisted virtualization (KVM + Firecracker / QEMU). Each sandbox runs its own dedicated Linux kernel with separate memory and CPU isolation. When Cairn detonates arbitrary OS command injection (`GET /list?folder=;id`), the exploit is physically locked inside the guest microVM.
* **Network Containment**: Docker network controls on shared hosts can be bypassed with host-network misconfigurations or socket mounts. Celesto enforces true hardware-level network policy at the hypervisor boundary.

### vs. E2B & Others
* **Local + Cloud Open-Source Parity**: The exact same Celesto API runs locally (on Linux/macOS with KVM) and in Celesto Cloud (Apache 2.0).
* **Stop/Start Persistence**: Celesto preserves root disk state across stop/start cycles. Cairn leverages this for **Step-7 Failure Recovery**: when an app crashes mid-investigation, Cairn stops and resumes the same sandbox, preserving the extracted source and installed dependencies without wasting credits on re-downloading.

---

## 3. "What would break at 1,000 users?"

1. **Concurrent Sandbox Quotas**:
   * *The bottleneck*: Cloud API accounts have concurrency caps (trial allows 1 concurrent sandbox, returning HTTP 429 on concurrent attempts, as documented in our `reports/concurrency.json`).
   * *How Cairn handles it*: Cairn decouples intake from execution using an asynchronous PostgreSQL ledger queue (`RunRepository` / `WebStore`) and background workers.
2. **Disk & Resource Retention**:
   * *The bottleneck*: 1,000 stopped sandboxes would accumulate storage costs and hit tenant disk limits.
   * *How Cairn handles it*: Strict lifecycle hygiene (`reports/lifecycle.json`). Every sandbox is guaranteed to be deleted on completion, crash, or `SIGINT`/`SIGTERM` interrupt.
3. **LLM Provider Throughput**:
   * *The bottleneck*: 1,000 concurrent agents calling structured tools would hit TPM/RPM rate limits on OpenAI-compatible gateways. Cairn uses bounded step budgets (capped at 5-10 turns) with automatic controller fallback if the LLM stalls.

---

## 4. Honest Product Feedback for the Founder

Founders value constructive, experienced feedback from developers who actually pushed their SDK to the limits:

1. **Granular Transitional Network Policy in the Python SDK**:
   * *The gotcha*: The SDK currently provides binary network settings (`mode: "off"` vs. open). 
   * *The feature request*: Real security evaluation needs a **transitional network lifecycle**: allow outbound traffic to PyPI/npm *only* during dependency installation, then automatically drop to loopback-only *before* launching the untrusted subject application. Cairn currently works around this by sequencing guest helpers, but a native SDK API (`computer.set_network_policy("loopback_only")`) would be a massive differentiator.
2. **Standardized Process Readiness & Port Probing**:
   * *The gotcha*: When launching background services inside the guest, `computer.run()` returns immediately. Developers currently have to write custom loopback socket polling or check `/proc/net/tcp` to know when an HTTP fixture is ready.
   * *The feature request*: A built-in `computer.wait_for_port(port, timeout=30)` method in the Celesto SDK.

