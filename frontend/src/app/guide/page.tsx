import Link from "next/link";
import {
  ArrowRight,
  Layers,
} from "lucide-react";
import { WorkspaceShell } from "@/components/workspace-shell";
import { signedIn, localAccessEnabled } from "@/lib/auth";

export const metadata = { title: "Using Cairn · Architecture & User Guide" };

export default async function Page() {
  const isAuth = await signedIn();
  const isLocal = await localAccessEnabled();
  return (
    <WorkspaceShell operator={isAuth} local={isLocal}>
      <div className="guide-container">
        <div className="guide-hero">
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 10px",
              borderRadius: "4px",
              background: "var(--app-soft)",
              color: "var(--accent)",
              fontSize: "12px",
              fontWeight: 700,
              marginBottom: "12px",
            }}
          >
            <Layers size={14} /> ARCHITECTURE & VERIFICATION
          </div>
          <h1>Deterministic Security Verification in MicroVMs</h1>
          <p>
            Cairn is an autonomous verification agent that validates operating-system
            command injection (CWE-78) claims inside hardware-isolated microVMs.
            Instead of relying on LLM guesswork or static scanning, Cairn boots the application,
            audits the code, and produces cryptographic, reproducible proof.
          </p>
          <div style={{ display: "flex", gap: "12px", marginTop: "18px", flexWrap: "wrap" }}>
            <Link
              href="/operator/investigations/new"
              className="button primary-button"
              style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
            >
              Start an investigation <ArrowRight size={15} />
            </Link>
            <Link
              href="/investigations/northstar-vulnerable"
              className="subtle-button"
              style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
            >
              Explore sample finding <ArrowRight size={15} />
            </Link>
          </div>
        </div>

        <section className="content-panel">
          <h2>The 5-Stage Verification Lifecycle</h2>
          <p>
            Every submission runs through a strict, deterministic evaluation pipeline designed for complete safety and repeatability.
          </p>

          <div className="guide-grid">
            <div className="guide-card">
              <span className="guide-card-num">Phase 01</span>
              <h3>Intake & Sockets</h3>
              <p>
                Provide a public GitHub repo or upload a <code>.tar.gz</code> archive (up to 50 MiB).
                Cairn automatically scans guest network sockets (<code>/proc/net/tcp</code>) to adopt the listening HTTP port without manual configuration.
              </p>
            </div>

            <div className="guide-card">
              <span className="guide-card-num">Phase 02</span>
              <h3>MicroVM Isolation</h3>
              <p>
                A dedicated Celesto Firecracker microVM instance is booted with hardware-assisted virtualization (KVM).
                The guest kernel isolates memory, process execution, and enforces strict egress network restrictions during probing.
              </p>
            </div>

            <div className="guide-card">
              <span className="guide-card-num">Phase 03</span>
              <h3>Dependency SBOM</h3>
              <p>
                Packages are installed inside Celesto according to declared manifests (<code>requirements.txt</code>, <code>package.json</code>, or <code>go.mod</code>).
                All package installation logs and version outputs are audited and saved to the report.
              </p>
            </div>

            <div className="guide-card">
              <span className="guide-card-num">Phase 04</span>
              <h3>Autonomous Code Audit</h3>
              <p>
                The Cairn agent reads candidate route definitions (<code>inspect_source</code>) without modifying files.
                It identifies dangerous sinks like <code>os.system()</code>, <code>os.popen()</code>, or <code>subprocess(shell=True)</code>.
              </p>
            </div>

            <div className="guide-card">
              <span className="guide-card-num">Phase 05</span>
              <h3>Independent Recheck</h3>
              <p>
                To eliminate hallucinations and false positives, every positive result triggers an independent control-plane verification using a fresh, secret proof marker before confirming a verdict.
              </p>
            </div>

            <div className="guide-card">
              <span className="guide-card-num">Phase 06</span>
              <h3>Teardown & Cleanup</h3>
              <p>
                Once execution completes, the microVM instance is permanently destroyed. Zero residual state or containers remain on disk.
              </p>
            </div>
          </div>
        </section>

        <section className="content-panel">
          <h2>Understanding Cairn Verdicts</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginTop: "16px" }}>
            <div style={{ padding: "16px", border: "1px solid var(--app-line)", borderRadius: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                <span className="status-badge verified">Vulnerability verified</span>
                <strong>Exploit confirmed by independent recheck</strong>
              </div>
              <p style={{ margin: 0, fontSize: "13px", color: "var(--app-muted)" }}>
                The probe successfully achieved command execution, and the control plane independently confirmed reproduction using a fresh, non-deterministic proof marker. Actionable remediation advice and copyable engineering tickets are provided.
              </p>
            </div>

            <div style={{ padding: "16px", border: "1px solid var(--app-line)", borderRadius: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                <span className="status-badge not_reproduced">Not reproduced</span>
                <strong>The claim was rejected under tested conditions</strong>
              </div>
              <p style={{ margin: 0, fontSize: "13px", color: "var(--app-muted)" }}>
                The application responded safely without executing commands. Cairn distinguishes between a safe/sanitized input, an argument-vector implementation, or a route that was deleted/missing (HTTP 404).
              </p>
            </div>

            <div style={{ padding: "16px", border: "1px solid var(--app-line)", borderRadius: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                <span className="status-badge inconclusive">Inconclusive</span>
                <strong>Could not settle with certainty</strong>
              </div>
              <p style={{ margin: 0, fontSize: "13px", color: "var(--app-muted)" }}>
                The application failed to start, dependencies could not resolve, or the step budget was exhausted without observing conclusive proof.
              </p>
            </div>
          </div>
        </section>

        <section className="content-panel">
          <h2>Safety Philosophy: Harmless Proof Markers</h2>
          <p>
            Traditional scanners often attempt dangerous payloads (such as reverse shells, downloading remote scripts, or writing to sensitive system directories).
          </p>
          <p style={{ marginTop: "10px" }}>
            <strong>Cairn strictly uses benign proof markers:</strong>
          </p>
          <ul className="plain-list" style={{ marginTop: "10px", lineHeight: "1.8" }}>
            <li>• Probes use non-destructive triggers like <code>touch /tmp/cairn-markers/probe</code>.</li>
            <li>• The test harness checks if the marker file was created on the guest filesystem.</li>
            <li>• Outbound traffic from the target application is isolated to prevent accidental data exfiltration or unintended port scanning.</li>
            <li>• Probing is strictly bounded to the guest loopback (<code>127.0.0.1</code>).</li>
          </ul>
        </section>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBlock: "30px" }}>
          <Link href="/operator" className="subtle-button">
            ← Back to Investigations
          </Link>
          <Link href="/operator/investigations/new" className="button primary-button">
            New investigation <ArrowRight size={15} />
          </Link>
        </div>
      </div>
    </WorkspaceShell>
  );
}
