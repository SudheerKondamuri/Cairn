# Open-Source Contribution Draft for CelestoAI/celesto

> **Hackathon Tie-Breaker**: Submitting a well-written, high-value issue or PR to [CelestoAI/celesto](https://github.com/CelestoAI/celesto) is a documented tie-breaker for top placement.
> 
> You can open this issue directly under **Issues → New Issue** on `CelestoAI/celesto`.

---

### **Issue Title**:
`[Feature Request] Dynamic transitional network policy: allow outbound during dependency installation then lock to loopback`

### **Issue Category**:
`Feature / Architecture`

### **Body**:

#### Problem Summary
When building AI security investigation agents or code-evaluating agents (such as Cairn) that run untrusted third-party repositories inside Celesto microVMs, there is a fundamental tension in network policy:

1. **Dependency Installation**: Real-world applications require outbound internet access to fetch packages from PyPI, npm, or Go module proxies (e.g. `pip install -r requirements.txt`).
2. **Exploitation & Detonation**: Once the untrusted code starts running and the AI agent begins probing endpoints or reproducing vulnerabilities (e.g., CWE-78 command injection or prompt injection), outbound internet access **must be immediately revoked** to prevent:
   - Prompt-injection exfiltration of environment tokens.
   - Arbitrary outbound reverse shells triggered by untrusted payloads.

#### Current Limitation in the Python SDK
Currently, `Computer(provider="cloud", internet_settings={"mode": "off"})` or `_network_off(computer)` configures network access only at sandbox creation time. 
If network is enabled to permit `pip install`, it currently remains open for the lifetime of that sandbox session, unless custom host/guest firewall teardown is improvised. Conversely, creating the sandbox in offline mode prevents downloading runtime packages for arbitrary GitHub repositories.

#### Proposed Solution / API Enhancement
Expose a dynamic network transition method on the `Computer` object:

```python
from celesto import Computer

with Computer(provider="cloud") as computer:
    # Phase 1: Allow outbound package installation
    computer.set_network_policy(mode="open") # or allowlisted registry hosts
    computer.run("pip install -r requirements.txt")

    # Phase 2: Lock down network before executing untrusted app
    computer.set_network_policy(mode="loopback_only")
    computer.run("python app.py &")

    # Phase 3: Run agent probe loop - zero outbound exfiltration risk
    ...
```

#### Why This Matters for the Celesto Ecosystem
This capability elevates Celesto from general-purpose sandbox execution to the premier runtime for **adversarial AI security and untrusted code detonation**, providing a native hypervisor-level guarantee that cannot be replicated in ordinary shared Docker containers.

---
*Context from Cairn (Celesto Hackathon): Tested across 20 fresh microVM runs with prompt-injection containment verification.*

