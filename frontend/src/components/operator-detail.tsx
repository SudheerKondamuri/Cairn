"use client";
import Link from "next/link";
import { useState, useEffect } from "react";
import {
  ArrowLeft,
  Clock,
  Radio,
  RefreshCw,
  Terminal,
  XCircle,
  CheckCircle2,
  Cpu,
  Layers,
} from "lucide-react";
import { useRemote } from "@/lib/use-remote";
import { formatDate, isReport } from "@/lib/reports";
import { InvestigationActions } from "./investigation-actions";
import { ReportView } from "./report-view";

type RecordData = {
  investigation_id: string;
  status: string;
  report: string;
  manifest: unknown;
  result: unknown;
  error: string | null;
  created_at: string;
  updated_at: string;
  events: { message: string; created_at: string }[];
  cancel_requested: boolean;
  shared: boolean;
};

const isTerminal = (data: RecordData) =>
  ["completed", "failed", "cancelled"].includes(data.status);

export function OperatorDetail({ id }: { id: string }) {
  const { data, error, loading, reload, updated } = useRemote<RecordData>(
    `/api/operator/investigations/${id}`,
    2_500,
    isTerminal,
  );

  const [clock, setClock] = useState(() => Date.now());
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    if (!data || !["queued", "running"].includes(data.status)) return;
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [data?.status]);

  async function cancelInvestigation() {
    setCancelling(true);
    try {
      await fetch(`/api/operator/investigations/${id}/cancel`, { method: "POST" });
      reload();
    } catch {
      // Ignored
    } finally {
      setCancelling(false);
    }
  }

  if (error) {
    return (
      <div className="error-notice" role="alert">
        <strong>Connection needs attention</strong>
        <p>{error}</p>
        <button onClick={reload} className="subtle-button">
          Refresh
        </button>
        <Link href="/operator/sign-in">Sign in again</Link>
      </div>
    );
  }

  if (!data && loading) {
    return (
      <div className="loading-state" role="status">
        Loading investigation {id}…
      </div>
    );
  }

  if (!data) return null;

  // Case 1: Finished with full Report
  if (data.status === "completed" && isReport(data.result)) {
    return (
      <>
        <ReportView
          report={data.result}
          title="Investigation result"
          recorded={false}
          back="/operator"
          download={`/api/operator/investigations/${id}/report`}
        />
        <InvestigationActions
          id={id}
          status={data.status}
          result={data.result}
          events={data.events || []}
          cancelRequested={data.cancel_requested}
          shared={data.shared}
          reload={reload}
        />
      </>
    );
  }

  // Case 2: LIVE RUNNING OR QUEUED (MISSION CONTROL VIEW)
  const isLive = ["queued", "running"].includes(data.status);
  const events = data.events || [];
  const startTimestamp = events.length > 0
    ? new Date(events[0].created_at).getTime()
    : new Date(data.created_at).getTime();
  const elapsedSeconds = Math.max(0, Math.floor((clock - startTimestamp) / 1000));

  // Determine active pipeline stage monotonically
  let currentStep = 1;
  for (const ev of events) {
    const msg = ev.message.toLowerCase();
    if (msg.includes("upload") || msg.includes("dependencies") || msg.includes("dependency")) {
      currentStep = Math.max(currentStep, 2);
    }
    if (
      msg.includes("starting supplied application") ||
      msg.includes("ready on guest loopback") ||
      msg.includes("auto-adopting")
    ) {
      currentStep = Math.max(currentStep, 3);
    }
    if (msg.includes("running bounded") || msg.includes("tool:") || msg.includes("inspect")) {
      currentStep = Math.max(currentStep, 4);
    }
    if (msg.includes("verdict") || msg.includes("recheck") || msg.includes("completed")) {
      currentStep = Math.max(currentStep, 5);
    }
  }

  if (isLive) {
    return (
      <>
        <Link className="back-link" href="/operator">
          <ArrowLeft size={15} />
          Investigations
        </Link>

        <div className="page-heading detail-heading">
          <div>
            <div className="detail-label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span className={`status-badge ${data.status}`}>
                <span className="live-pulse-dot" />
                {data.status === "queued" ? "Queued in scheduler" : "MicroVM execution active"}
              </span>
              <span>Started {formatDate(data.created_at)}</span>
            </div>
            <h1>{data.status === "queued" ? "Waiting for sandbox allocation" : "Investigation in progress"}</h1>
            <p>
              Execution is isolated inside a dedicated Celesto Firecracker microVM. Telemetry updates automatically.
            </p>
            <code className="detail-id">{id}</code>
          </div>
          <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
            <span
              style={{
                fontFamily: "var(--mono)",
                fontSize: "12px",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 12px",
                borderRadius: "5px",
                background: "var(--app-soft)",
                color: "var(--app-text)",
                border: "1px solid var(--app-line)",
              }}
            >
              <Clock size={13} /> {elapsedSeconds}s
            </span>
            <button className="subtle-button" disabled={loading} onClick={reload}>
              <RefreshCw size={14} />
              Refresh
            </button>
            <button
              className="subtle-button"
              disabled={cancelling || data.cancel_requested}
              onClick={cancelInvestigation}
              style={{ color: "var(--accent)" }}
            >
              <XCircle size={14} />
              {data.cancel_requested || cancelling ? "Cancelling…" : "Cancel run"}
            </button>
          </div>
        </div>

        {/* Visual 5-Stage Pipeline */}
        <div className="live-pipeline-bar">
          {[
            { num: "01", name: "Sandbox Boot", desc: "Firecracker KVM" },
            { num: "02", name: "Dependencies", desc: "Package setup" },
            { num: "03", name: "Application", desc: "Process & port" },
            { num: "04", name: "Security Audit", desc: "Dynamic probe" },
            { num: "05", name: "Verification", desc: "Independent check" },
          ].map((stage, idx) => {
            const stepNum = idx + 1;
            const isDone = currentStep > stepNum;
            const isActive = currentStep === stepNum;
            return (
              <div
                key={stage.num}
                className={`live-pipeline-step ${isActive ? "active" : isDone ? "completed" : ""}`}
              >
                <span>Phase {stage.num}</span>
                <strong>{stage.name}</strong>
                <span style={{ fontSize: "11px", color: "var(--app-muted)" }}>{stage.desc}</span>
              </div>
            );
          })}
        </div>

        {/* Live Stream Box */}
        <div className="live-stream-box">
          <div className="live-stream-header">
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <Terminal size={14} />
              <span>GUEST TELEMETRY LOG</span>
              <span style={{ color: "var(--app-muted)" }}>·</span>
              <span style={{ color: "var(--app-muted)", fontWeight: "normal" }}>
                {events.length} event{events.length === 1 ? "" : "s"}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--app-muted)", fontSize: "11px" }}>
              <Radio size={12} />
              <span>Streaming</span>
            </div>
          </div>
          <ul className="live-event-list">
            {events.length > 0 ? (
              [...events].reverse().map((ev, index) => {
                const isLatest = index === 0;
                const isToolStart = ev.message.startsWith("Tool: ");
                const isToolDone = ev.message.startsWith("Tool completed: ");
                return (
                  <li
                    key={`${ev.created_at}-${events.length - index}`}
                    className={`live-event-item ${isLatest ? "is-latest" : ""}`}
                  >
                    <span className="live-event-time">
                      {new Date(ev.created_at).toLocaleTimeString()}
                    </span>
                    <div style={{ flex: 1, display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                      {isToolStart ? (
                        <>
                          <span className="tool-chip">dispatch</span>
                          <code>{ev.message.slice(6)}</code>
                        </>
                      ) : isToolDone ? (
                        <>
                          <span className="tool-chip done">return</span>
                          <code>{ev.message.slice(16)}</code>
                        </>
                      ) : (
                        <span>{ev.message}</span>
                      )}
                      {isLatest && (
                        <span className="status-badge running" style={{ padding: "1px 6px", fontSize: "10px" }}>
                          Current
                        </span>
                      )}
                    </div>
                  </li>
                );
              })
            ) : (
              <li className="live-event-item" style={{ color: "var(--app-muted)", padding: "24px" }}>
                Waiting for an available Celesto sandbox worker… The microVM allocation will begin momentarily.
              </li>
            )}
          </ul>
        </div>

        {/* Collapsed Submission Details Accordion */}
        <details className="content-panel" style={{ marginTop: "24px" }}>
          <summary style={{ cursor: "pointer", fontWeight: 600, color: "var(--app-muted)", fontSize: "13px" }}>
            View submitted claim & runtime configuration
          </summary>
          <div style={{ marginTop: "14px" }}>
            <h3>Submitted Claim</h3>
            <pre className="readable-pre">{data.report}</pre>
            <h3 style={{ marginTop: "14px" }}>Runtime Manifest</h3>
            <pre>{JSON.stringify(data.manifest, null, 2)}</pre>
          </div>
        </details>
      </>
    );
  }

  // Case 3: Failed or Cancelled State
  return (
    <>
      <Link className="back-link" href="/operator">
        <ArrowLeft size={15} />
        Investigations
      </Link>
      <div className="page-heading">
        <div>
          <div className="detail-label">
            <span className={`status-badge ${data.status}`}>
              {data.status === "cancelled" ? "Cancelled" : "Failed"}
            </span>
            <span>{formatDate(data.updated_at)}</span>
          </div>
          <h1>{data.status === "cancelled" ? "Investigation Cancelled" : "Investigation Interrupted"}</h1>
          <code className="detail-id">{id}</code>
        </div>
        <button className="subtle-button" disabled={loading} onClick={reload}>
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      <div className="job-state-panel">
        <h2>{data.status === "cancelled" ? "Run halted by user request" : "Execution halted with an error"}</h2>
        <p>
          {data.status === "cancelled"
            ? "The investigation was cancelled. Sandbox cleanup was performed."
            : "Review the recorded error below. The sandbox environment has been torn down."}
        </p>
        {data.error && <pre className="recorded-error">{data.error}</pre>}
      </div>

      {events.length > 0 && (
        <div className="live-stream-box" style={{ marginTop: "20px" }}>
          <div className="live-stream-header">
            <span>ACTIVITY LOG PRIOR TO HALT ({events.length} events)</span>
          </div>
          <ul className="live-event-list">
            {[...events].reverse().map((ev, i) => (
              <li key={`${ev.created_at}-${events.length - i}`} className="live-event-item">
                <span className="live-event-time">{new Date(ev.created_at).toLocaleTimeString()}</span>
                <span>{ev.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <InvestigationActions
        id={id}
        status={data.status}
        result={data.result}
        events={data.events || []}
        cancelRequested={data.cancel_requested}
        shared={data.shared}
        reload={reload}
      />
    </>
  );
}
