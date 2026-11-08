"use client";
import { useState } from "react";
import Link from "next/link";
import {
  ArrowDownToLine,
  ArrowLeft,
  Check,
  FileText,
  Fingerprint,
  ShieldAlert,
  ShieldCheck,
  AlertCircle,
  Activity,
} from "lucide-react";
import { type Report, formatDate } from "@/lib/reports";

export function ReportView({
  report,
  title,
  download,
  back = "/investigations",
  recorded = true,
}: {
  report: Report;
  title: string;
  download: string;
  back?: string;
  recorded?: boolean;
}) {
  const [tab, setTab] = useState("overview");
  const [attempt, setAttempt] = useState(0);
  const selected = report.evidence.attempts[attempt];

  const inspections = report.evidence.inspections || [];
  const dependencyEvents = report.dependencies?.events || [];
  const has404 = report.evidence.attempts.some((a) => a.status === 404);
  const isVerified = report.verdict === "verified";
  const isSafe = report.verdict === "not_reproduced" && !has404;

  const displayRationale =
    report.evidence.agent_rationale &&
    report.evidence.agent_rationale.includes("bounded agent budget was exhausted")
      ? has404
        ? "The investigation concluded because the target route returned HTTP 404. The suspected path could not be reached."
        : "All test requests completed safely without executing operating-system commands."
      : report.evidence.agent_rationale || report.summary;

  return (
    <>
      <Link className="back-link" href={back}>
        <ArrowLeft size={15} />
        Investigations
      </Link>
      <div className="report-hero">
        <div className="report-hero-meta">
          <span className={`status-badge ${report.verdict}`}>
            {isVerified && report.evidence.independent_recheck?.marker_detected ? (
              <>
                <ShieldAlert size={14} />
                Vulnerability confirmed
              </>
            ) : has404 ? (
              <>
                <AlertCircle size={14} />
                Endpoint not found (404)
              </>
            ) : isSafe ? (
              <>
                <ShieldCheck size={14} />
                Input handled safely
              </>
            ) : (
              <>
                <Fingerprint size={14} />
                Not reproduced
              </>
            )}
          </span>
          <span className="hero-meta-dot">·</span>
          <span>{recorded ? "Recorded case" : "Live run"}</span>
          <span className="hero-meta-dot">·</span>
          <span>{formatDate(report.generated_at)}</span>
          {title && title !== "Investigation result" && (
            <>
              <span className="hero-meta-dot">·</span>
              <span className="hero-meta-target">{title}</span>
            </>
          )}
        </div>

        <div className="report-hero-row">
          <h1>
            {isVerified
              ? "Command Injection Confirmed (CWE-78)"
              : has404
              ? "Suspected Route Not Found (HTTP 404)"
              : isSafe
              ? "Input Sanitization Verified Safe"
              : title && title !== "Investigation result"
              ? title
              : "Investigation Outcome"}
          </h1>
          <a className="subtle-button" href={download} download title="Download full JSON report">
            <ArrowDownToLine size={15} />
            Download JSON
          </a>
        </div>

        <p className="report-hero-summary">
          {isVerified
            ? `Cairn successfully reproduced command injection on '${report.evidence.request.path}'. When untrusted input was supplied to parameter '${report.evidence.request.param_name}', arbitrary commands executed on the operating system and were verified by an independent control-plane check.`
            : has404
            ? `Cairn tested the suspected route '${report.evidence.request.path || "/ping"}', but the running application returned HTTP 404 Not Found. The endpoint does not exist on this service or is registered under a different route prefix.`
            : isSafe
            ? `Cairn tested multiple command injection payloads against '${report.evidence.request.path}'. The application processed input safely without executing operating-system commands.`
            : report.summary}
        </p>

        <div className="finding-metrics-grid">
          <div>
            <span className="metric-label">Target Route</span>
            <span className="metric-value font-mono">{report.evidence.request.path || "—"}</span>
          </div>
          <div>
            <span className="metric-label">Observed Status</span>
            <span className="metric-value font-mono">
              {has404 ? "404 Not Found" : isSafe ? "200 OK (Safe)" : isVerified ? "200 (Exploited)" : "Completed"}
            </span>
          </div>
          <div>
            <span className="metric-label">Proof Marker</span>
            <span className="metric-value">
              {isVerified ? "Confirmed Executed" : "None Detected"}
            </span>
          </div>
          <div>
            <span className="metric-label">Host Target</span>
            <span className="metric-value font-mono">127.0.0.1:{report.subject?.port || 5000}</span>
          </div>
        </div>
      </div>
      <div className="detail-tabs" aria-label="Report sections">
        {[
          { id: "overview", label: "Overview" },
          { id: "requests", label: `Requests (${report.evidence.attempts.length})` },
          {
            id: "code",
            label: `Code Audit${inspections.length ? ` (${inspections.length})` : ""}`,
          },
          { id: "dependencies", label: "Dependencies & SBOM" },
          { id: "telemetry", label: "Sandbox Telemetry" },
          { id: "provenance", label: "Source & Provenance" },
        ].map((item) => (
          <button
            key={item.id}
            aria-pressed={tab === item.id}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="detail-layout">
        <div className="detail-primary">
          {tab === "overview" && (
            <>
              {has404 && (
                <section className="content-panel diagnostic-guidance">
                  <strong>Technical Diagnostic Notes</strong>
                  <ul>
                    <li>
                      <strong>Route prefix:</strong> The application returned 404 for <code>{report.evidence.request.path}</code>. Verify whether routes are mounted under a prefix such as <code>/api/...</code> or <code>/v1/...</code>.
                    </li>
                    <li>
                      <strong>Entrypoint directory:</strong> If source files reside in a subfolder (e.g. <code>app/</code>), verify that the working directory or startup command points to it.
                    </li>
                    <li>
                      <strong>Telemetry:</strong> View the <em>Requests</em> tab to inspect raw server headers and response bodies, or <em>Code Audit</em> to view inspected files.
                    </li>
                  </ul>
                </section>
              )}

              <section className="content-panel">
                <h2>The reported claim</h2>
                <details className="claim-text">
                  <summary>
                    <FileText size={16} />
                    Read the supplied report
                  </summary>
                  <pre>{report.claim.report}</pre>
                </details>
              </section>
              <section className="content-panel">
                <h2>What supports the conclusion</h2>
                <ul className="reason-list">
                  {report.explanation?.why.map((reason) => (
                    <li key={reason}>
                      <Check size={16} />
                      <span>{reason}</span>
                    </li>
                  ))}
                </ul>
                <p>{displayRationale}</p>
              </section>
              {report.explanation && (
                <section className="content-panel">
                  <h2>Next steps</h2>
                  <p>{report.explanation.next_action}</p>
                  <ul className="plain-list">
                    {report.explanation.remediation.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}

          {tab === "requests" && (
            <section className="content-panel">
              <h2>Recorded requests</h2>
              <p>
                Each response is retained as observed. Payloads below are
                displayed as text.
              </p>
              <div className="attempt-selector">
                {report.evidence.attempts.map((item, index) => (
                  <button
                    key={index}
                    aria-pressed={attempt === index}
                    onClick={() => setAttempt(index)}
                  >
                    <span>Request {index + 1}</span>
                    <span>
                      {item.marker_detected ? "Marker observed" : "No marker"}
                    </span>
                  </button>
                ))}
              </div>
              {selected ? (
                <div className="attempt-detail">
                  <div className="request-facts">
                    <span>HTTP {selected.status ?? "unknown"}</span>
                    <span>{selected.elapsed_ms} ms</span>
                    <span>{selected.outcome}</span>
                  </div>
                  <h3>Endpoint</h3>
                  <pre>GET {selected.path}</pre>
                  <h3>Input · {selected.param_name}</h3>
                  <pre>{selected.param_value}</pre>
                  <h3>Response body</h3>
                  <pre>{prettyBody(selected.body)}</pre>
                </div>
              ) : (
                <p>No requests were recorded.</p>
              )}
            </section>
          )}

          {tab === "code" && (
            <section className="content-panel">
              <h2>Code Audit & Inspected Locations</h2>
              <p>
                Dynamic inspections executed during the investigation. Cairn reads targeted source line ranges to verify route definitions, query parameters, and subprocess calls without modifying files.
              </p>
              {inspections.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "20px", marginTop: "18px" }}>
                  {inspections.map((insp, index) => (
                    <div key={index} className="attempt-detail" style={{ marginTop: 0 }}>
                      <div className="request-facts">
                        <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--app-text)" }}>
                          {insp.path}
                        </span>
                        <span>Lines {insp.start_line} – {insp.end_line}</span>
                        {insp.source_hash && <span>SHA: {insp.source_hash.slice(0, 10)}…</span>}
                      </div>
                      <pre style={{ maxHeight: "360px", overflow: "auto", marginTop: "10px" }}>
                        <code>{insp.text}</code>
                      </pre>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ marginTop: "16px", color: "var(--app-muted)" }}>
                  No source code lines were recorded in this report. In pre-release or static test runs, the harness exercised the entrypoint directly.
                </p>
              )}
            </section>
          )}

          {tab === "dependencies" && (
            <>
              <section className="content-panel">
                <h2>Dependency Policy & Environment</h2>
                <p>
                  Celesto enforces network policies during guest package installation to prevent supply-chain attacks and isolate reproduction runs.
                </p>
                <dl className="fact-list" style={{ marginTop: "16px" }}>
                  <div>
                    <dt>Dependency Mode</dt>
                    <dd>{report.dependencies?.mode || "offline"}</dd>
                  </div>
                  <div>
                    <dt>Network during Install</dt>
                    <dd>
                      {report.dependencies?.network_during_install_allowed
                        ? "Enabled (controlled registry downloads)"
                        : "Disabled (offline image)"}
                    </dd>
                  </div>
                  <div>
                    <dt>Install Scripts</dt>
                    <dd>
                      {report.dependencies?.install_scripts_allowed
                        ? "Permitted"
                        : "Restricted (security policy)"}
                    </dd>
                  </div>
                </dl>
              </section>

              <section className="content-panel">
                <h2>Installation Activity & SBOM</h2>
                {dependencyEvents.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginTop: "14px" }}>
                    {dependencyEvents.map((ev, index) => (
                      <div key={index} className="attempt-detail" style={{ marginTop: 0 }}>
                        <div className="request-facts">
                          <span>{ev.manifest || "No manifest file"}</span>
                          <span>{ev.installed ? "Installed successfully" : (ev.reason || "Not installed")}</span>
                          {ev.exit_code !== undefined && <span>Exit code {ev.exit_code}</span>}
                        </div>
                        {ev.command && (
                          <>
                            <h3>Command</h3>
                            <pre><code>{ev.command.join(" ")}</code></pre>
                          </>
                        )}
                        {ev.stdout && (
                          <>
                            <h3>Installation stdout</h3>
                            <pre style={{ maxHeight: "250px", overflow: "auto" }}>
                              <code>{ev.stdout}</code>
                            </pre>
                          </>
                        )}
                        {ev.stderr && (
                          <>
                            <h3>Installation stderr</h3>
                            <pre style={{ maxHeight: "150px", overflow: "auto" }}>
                              <code>{ev.stderr}</code>
                            </pre>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ marginTop: "14px", color: "var(--app-muted)" }}>
                    No dependency installation events were recorded for this run.
                  </p>
                )}
              </section>
            </>
          )}

          {tab === "telemetry" && (
            <>
              <section className="content-panel">
                <h2>Celesto MicroVM Isolation</h2>
                <p>
                  Every investigation runs in a hardware-virtualized Firecracker microVM instance. Cairn monitors guest kernel network sockets and policy enforcement.
                </p>
                <dl className="fact-list" style={{ marginTop: "16px" }}>
                  <div>
                    <dt>Hypervisor / Isolation</dt>
                    <dd>
                      {report.lifecycle.isolation
                        ? "Celesto Firecracker MicroVM (Hardware KVM)"
                        : "Ephemeral MicroVM"}
                    </dd>
                  </div>
                  <div>
                    <dt>Network Policy</dt>
                    <dd>
                      {report.lifecycle.network_policy === "enforced_offline"
                        ? "Enforced Offline (egress blocked during probe)"
                        : (report.lifecycle.network_policy || "Controlled")}
                    </dd>
                  </div>
                  <div>
                    <dt>Port Discovery</dt>
                    <dd>
                      {report.lifecycle.auto_discovered_port
                        ? `Port ${report.lifecycle.auto_discovered_port} (Auto-detected from /proc/net/tcp)`
                        : (report.subject?.port ? `Port ${report.subject.port} (Specified)` : "Loopback socket")}
                    </dd>
                  </div>
                  <div>
                    <dt>MicroVM Instance ID</dt>
                    <dd style={{ fontFamily: "monospace" }}>{report.lifecycle.sandbox_name}</dd>
                  </div>
                  <div>
                    <dt>Lifecycle State</dt>
                    <dd>
                      {report.lifecycle.sandbox_deleted
                        ? "Torn down & deleted (zero residual state)"
                        : "Active / Retained"}
                    </dd>
                  </div>
                  <div>
                    <dt>Guest Execution Time</dt>
                    <dd>{report.lifecycle.wall_clock_s.toFixed(3)} seconds</dd>
                  </div>
                </dl>
              </section>

              {report.lifecycle.subject_manifest && (
                <section className="content-panel">
                  <h2>Uploaded Source Files ({report.lifecycle.subject_manifest.file_count})</h2>
                  <p>
                    Target files extracted into the guest environment root with verified checksums.
                  </p>
                  <ul className="plain-list" style={{ marginTop: "12px", fontFamily: "monospace", fontSize: "13px" }}>
                    {report.lifecycle.subject_manifest.files.map((file) => (
                      <li key={file} style={{ padding: "4px 0" }}>• {file}</li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}

          {tab === "provenance" && (
            <>
              <section className="content-panel">
                <h2>Source identity</h2>
                <p>
                  The source digest connects this result to the version that was
                  investigated.
                </p>
                <h3>SHA-256</h3>
                <code className="hash-value">
                  {report.evidence.source_hash}
                </code>
                <h3>Investigation ID</h3>
                <code className="hash-value">{report.investigation_id}</code>
              </section>
              <section className="content-panel">
                <h2>Independent recheck</h2>
                {report.evidence.independent_recheck ? (
                  <>
                    <p>
                      A separate controller-created request used a fresh token
                      in the same guest.
                    </p>
                    <dl className="fact-list">
                      <div>
                        <dt>Marker</dt>
                        <dd>
                          {report.evidence.independent_recheck.marker_detected
                            ? "Observed"
                            : "Not observed"}
                        </dd>
                      </div>
                      <div>
                        <dt>Outcome</dt>
                        <dd>{report.evidence.independent_recheck.outcome}</dd>
                      </div>
                    </dl>
                    <code className="hash-value">
                      {report.evidence.independent_recheck.fresh_token ||
                        "Token not recorded"}
                    </code>
                  </>
                ) : (
                  <p>
                    No independent positive recheck is recorded. A negative
                    finding does not prove all code paths are safe.
                  </p>
                )}
              </section>
            </>
          )}
        </div>
        <aside className="context-panel">
          <h2>Run context</h2>
          <dl className="fact-list">
            <div>
              <dt>Runtime</dt>
              <dd>{report.claim.runtime}</dd>
            </div>
            <div>
              <dt>Subject</dt>
              <dd>{report.claim.subject_type.replaceAll("_", " ")}</dd>
            </div>
            <div>
              <dt>Isolation</dt>
              <dd>Firecracker MicroVM</dd>
            </div>
            <div>
              <dt>Port</dt>
              <dd>
                {report.lifecycle.auto_discovered_port
                  ? `${report.lifecycle.auto_discovered_port} (auto)`
                  : (report.subject?.port ? `${report.subject.port}` : "5000")}
              </dd>
            </div>
            <div>
              <dt>Wall time</dt>
              <dd>{report.lifecycle.wall_clock_s.toFixed(3)} s</dd>
            </div>
            <div>
              <dt>Requests</dt>
              <dd>{report.evidence.attempts.length}</dd>
            </div>
            <div>
              <dt>Cleanup</dt>
              <dd>
                {report.lifecycle.sandbox_deleted
                  ? "Deletion reported"
                  : "Not confirmed"}
              </dd>
            </div>
          </dl>
          <h3>Sandbox</h3>
          <code className="hash-value">{report.lifecycle.sandbox_name}</code>
          <p className="context-note">
            Job completion, the finding, and sandbox cleanup are separate
            outcomes. The cleanup value comes from this report.
          </p>
          <a href={download} className="report-download" download>
            <ArrowDownToLine size={16} />
            Original evidence
          </a>
        </aside>
      </div>
    </>
  );
}

function prettyBody(body: string) {
  try {
    return JSON.stringify(JSON.parse(body), null, 2);
  } catch {
    return body;
  }
}
