"use client";
import { useState } from "react";
import Link from "next/link";
import {
  ArrowDownToLine,
  ArrowLeft,
  Check,
  FileText,
  Fingerprint,
} from "lucide-react";
import { type Report, verdictLabel, formatDate } from "@/lib/reports";
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
  return (
    <>
      <Link className="back-link" href={back}>
        <ArrowLeft size={15} />
        Investigations
      </Link>
      <div className="page-heading detail-heading">
        <div>
          <div className="detail-label">
            <span className="status-badge neutral">
              {recorded ? "Recorded investigation" : "Completed investigation"}
            </span>
            <span>{formatDate(report.generated_at)}</span>
          </div>
          <h1>{title}</h1>
          <p>{report.summary}</p>
        </div>
        <a className="subtle-button" href={download} download>
          <ArrowDownToLine size={16} />
          Download JSON
        </a>
      </div>
      <div className="finding-banner">
        <div>
          <span>Finding</span>
          <h2>{verdictLabel(report.verdict)}</h2>
        </div>
        <span className={`status-badge ${report.verdict}`}>
          <Fingerprint size={14} />
          {report.verdict === "verified" &&
          report.evidence.independent_recheck?.marker_detected
            ? "Independent marker confirmed"
            : "No positive conclusion"}
        </span>
      </div>
      <div className="detail-tabs" aria-label="Report sections">
        {["overview", "requests", "provenance"].map((value) => (
          <button
            key={value}
            aria-pressed={tab === value}
            onClick={() => setTab(value)}
          >
            {value === "overview"
              ? "Overview"
              : value === "requests"
                ? `Requests (${report.evidence.attempts.length})`
                : "Source & provenance"}
          </button>
        ))}
      </div>
      <div className="detail-layout">
        <div className="detail-primary">
          {tab === "overview" && (
            <>
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
                <p>{report.evidence.agent_rationale || report.summary}</p>
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
