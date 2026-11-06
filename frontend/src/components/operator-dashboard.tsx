"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Plus, RefreshCw, Search, Inbox } from "lucide-react";
import { useRemote } from "@/lib/use-remote";
import { formatDate, verdictLabel } from "@/lib/reports";
type Row = {
  investigation_id: string;
  status: string;
  verdict: string | null;
  created_at: string;
  updated_at: string;
  runtime: string;
  subject_type: string;
  title: string;
};
export function OperatorDashboard() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [cursor, setCursor] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const params = new URLSearchParams({ q: search, status, cursor });
  const { data, error, loading, updated, reload } = useRemote<{
    items: Row[];
    next_cursor: string | null;
  }>(`/api/operator/investigations?${params}`);
  const health = useRemote<{ status: string }>("/api/operator/ready", 60_000);
  const [lookup, setLookup] = useState("");
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="breadcrumb">Operator workspace</p>
          <h1>Your investigations</h1>
          <p>Submit a claim, track the work, inspect the evidence.</p>
        </div>
        <Link
          className="button primary-button"
          href="/operator/investigations/new"
        >
          <Plus size={17} />
          New investigation
        </Link>
      </div>
      <div className="connection-strip">
        <span
          className={`mode-dot ${!health.error && health.data?.status === "ready" ? "connected" : ""}`}
        />
        <strong>
          {health.error
            ? "Service connection lost"
            : health.data?.status === "ready"
              ? "API and ledger reachable"
              : health.loading
                ? "Checking service…"
                : "Service unavailable"}
        </strong>
        <span>Worker availability is not reported by this endpoint.</span>
      </div>
      <form
        className="filter-bar"
        onSubmit={(event) => {
          event.preventDefault();
          setSearch(query);
          setCursor("");
          setHistory([]);
        }}
      >
        <label className="search-field">
          <Search size={17} />
          <span className="sr-only">Search private investigations</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search ID or report…"
            maxLength={100}
          />
        </label>
        <button className="subtle-button">Search</button>
        <label>
          <span className="sr-only">Job status</span>
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setCursor("");
              setHistory([]);
            }}
          >
            <option value="">All job states</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </label>
        <button
          type="button"
          className="icon-button"
          onClick={reload}
          aria-label="Refresh investigations"
          disabled={loading}
        >
          <RefreshCw size={17} />
        </button>
      </form>
      {error && (
        <div className="error-notice" role="alert">
          <strong>Couldn’t refresh investigations</strong>
          <p>{error}</p>
          <Link href="/operator/sign-in">Check operator access</Link>
        </div>
      )}
      {loading && !data ? (
        <div className="loading-state" role="status">
          Loading investigations…
        </div>
      ) : data?.items.length ? (
        <>
          <div
            className="table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Private investigation history"
          >
            <table className="run-table">
              <thead>
                <tr>
                  <th>Investigation</th>
                  <th>Job state</th>
                  <th>Finding</th>
                  <th>Created</th>
                  <th>
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.investigation_id}>
                    <td>
                      <Link
                        href={`/operator/investigations/${row.investigation_id}`}
                      >
                        <strong>{row.title || "Untitled investigation"}</strong>
                        <code>{row.investigation_id}</code>
                      </Link>
                    </td>
                    <td>
                      <span className={`status-badge ${row.status}`}>
                        {row.status}
                      </span>
                    </td>
                    <td>
                      {row.verdict
                        ? verdictLabel(row.verdict)
                        : "Not available yet"}
                    </td>
                    <td>{formatDate(row.created_at)}</td>
                    <td>
                      <Link
                        href={`/operator/investigations/${row.investigation_id}`}
                        aria-label={`Open ${row.investigation_id}`}
                      >
                        <ArrowRight size={18} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination">
            <button
              className="subtle-button"
              disabled={!history.length}
              onClick={() => {
                setCursor(history.at(-1) || "");
                setHistory(history.slice(0, -1));
              }}
            >
              Previous
            </button>
            <span>{data.items.length} investigations on this page</span>
            <button
              className="subtle-button"
              disabled={!data.next_cursor}
              onClick={() => {
                setHistory([...history, cursor]);
                setCursor(data.next_cursor || "");
              }}
            >
              Next
            </button>
          </div>
        </>
      ) : (
        !error && (
          <div className="empty-state">
            <Inbox size={32} />
            <h2>A clean slate.</h2>
            <p>Your first investigation starts with a report and its source.</p>
            <Link
              href="/operator/investigations/new"
              className="button primary-button"
            >
              Create an investigation
            </Link>
          </div>
        )
      )}
      <div className="lookup-panel">
        <div>
          <h2>Have an investigation ID?</h2>
          <p>Open a private record directly.</p>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (/^inv-[a-zA-Z0-9-]{1,100}$/.test(lookup))
              router.push(
                `/operator/investigations/${encodeURIComponent(lookup)}`,
              );
          }}
        >
          <label className="sr-only" htmlFor="lookup">
            Investigation ID
          </label>
          <input
            id="lookup"
            required
            pattern={"inv-[a-zA-Z0-9\\-]{1,100}"}
            placeholder="inv-…"
            value={lookup}
            onChange={(e) => setLookup(e.target.value)}
          />
          <button className="subtle-button">
            Open <ArrowRight size={15} />
          </button>
        </form>
      </div>
      {updated && (
        <p className="workspace-disclaimer">
          Last refreshed {updated.toLocaleTimeString()}. Updates pause while
          this tab is hidden.
        </p>
      )}
    </>
  );
}
