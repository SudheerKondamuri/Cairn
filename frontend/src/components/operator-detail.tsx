"use client";
import Link from "next/link";
import { ArrowLeft, RefreshCw } from "lucide-react";
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
    4_000,
    isTerminal,
  );
  return (
    <>
      {error && (
        <div className="error-notice" role="alert">
          <strong>Connection needs attention</strong>
          <p>{error}</p>
          <button onClick={reload} className="subtle-button">
            Refresh
          </button>
          <Link href="/operator/sign-in">Sign in again</Link>
        </div>
      )}
      {data?.status === "completed" && isReport(data.result) ? (
        <ReportView
          report={data.result}
          title="Investigation result"
          recorded={false}
          back="/operator"
          download={`/api/operator/investigations/${id}/report`}
        />
      ) : (
        <>
          <Link className="back-link" href="/operator">
            <ArrowLeft size={15} />
            Investigations
          </Link>
          <div className="page-heading">
            <div>
              <p className="breadcrumb">Private investigation</p>
              <h1>
                {data?.status === "cancelled"
                  ? "Investigation cancelled"
                  : data?.status === "failed"
                    ? "Investigation interrupted"
                    : data?.status === "completed"
                      ? "Investigation completed"
                      : "Work in progress"}
              </h1>
              <code className="detail-id">{id}</code>
            </div>
            <button
              className="subtle-button"
              disabled={loading}
              onClick={reload}
            >
              <RefreshCw size={16} />
              Refresh
            </button>
          </div>
          {!data && loading ? (
            <div className="loading-state" role="status">
              Loading the investigation…
            </div>
          ) : (
            data && (
              <>
                <div className="job-state-panel">
                  <span className={`status-badge ${data.status}`}>
                    {data.status}
                  </span>
                  <h2>
                    {data.status === "queued"
                      ? "Waiting for a worker."
                      : data.status === "running"
                        ? "The worker has claimed this job."
                        : data.status === "failed"
                          ? "The worker reported a failure."
                          : "The job has finished."}
                  </h2>
                  <p>
                    {data.status === "queued"
                      ? "The API accepted the submission. A sandbox has not been confirmed yet."
                      : data.status === "running"
                        ? "Follow the confirmed stages and tool activity below. This view refreshes automatically."
                        : data.status === "failed"
                          ? "No successful finding is implied. Inspect the recorded error before attempting a new investigation."
                          : "The result format could not be displayed. Download the original record for inspection."}
                  </p>
                  {data.error && (
                    <pre className="recorded-error">{data.error}</pre>
                  )}
                  {data.status === "completed" && (
                    <a
                      href={`/api/operator/investigations/${id}/report`}
                      download
                      className="subtle-button"
                    >
                      Download result
                    </a>
                  )}
                  <dl className="inline-facts">
                    <div>
                      <dt>Created</dt>
                      <dd>{formatDate(data.created_at)}</dd>
                    </div>
                    <div>
                      <dt>Last job update</dt>
                      <dd>{formatDate(data.updated_at)}</dd>
                    </div>
                    <div>
                      <dt>Cleanup</dt>
                      <dd>{isReport(data.result) ? data.result.lifecycle.sandbox_deleted ? "Sandbox deleted" : "Deletion not confirmed" : "Not reported in this record"}</dd>
                    </div>
                  </dl>
                </div>
                <section className="content-panel">
                  <h2>Submitted claim</h2>
                  <pre className="readable-pre">{data.report}</pre>
                  <details>
                    <summary>Runtime manifest</summary>
                    <pre>{JSON.stringify(data.manifest, null, 2)}</pre>
                  </details>
                </section>
              </>
            )
          )}
        </>
      )}
      {data && (
        <InvestigationActions
          id={id}
          status={data.status}
          result={data.result}
          events={data.events || []}
          cancelRequested={data.cancel_requested}
          shared={data.shared}
          reload={reload}
        />
      )}
      {updated && (
        <p className="workspace-disclaimer">
          Last checked {updated.toLocaleTimeString()}. No uncertain action is
          retried automatically.
        </p>
      )}
    </>
  );
}
