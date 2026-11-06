"use client";
import { useState } from "react";
import { useRemote } from "@/lib/use-remote";
import { formatDate } from "@/lib/reports";
type User = {
  account_id: string;
  suspended: boolean;
  run_limit: number;
  used: number;
  requested: boolean;
};
type Admin = {
  accounts: User[];
  trial: { run_limit: number; paused: boolean };
  jobs: { investigation_id: string; status: string; updated_at: string }[];
};
export function AdminConsole() {
  const { data, error, reload } = useRemote<Admin>(
    "/api/operator/admin",
    15000,
  );
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  async function update(body: object) {
    setBusy(true);
    try {
      const r = await fetch("/api/operator/admin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const response = await r.json();
      if (!r.ok) throw new Error(response.error);
      setMessage("Changes saved and recorded in the audit log.");
      reload();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Update failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Trial operations.</h1>
          <p>
            Manage access and capacity. Private investigation contents stay with
            their owners.
          </p>
        </div>
      </div>
      {error && (
        <p role="alert" className="error-notice">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="notice">
          {message}
        </p>
      )}
      {data && (
        <>
          <section className="content-panel">
            <h2>Live execution</h2>
            <p>
              The deployment allows {data.trial.run_limit} investigations.
              Per-account grants remain subject to this limit.
            </p>
            <button
              className="subtle-button"
              disabled={busy}
              onClick={() =>
                update({ action: "trial", paused: !data.trial.paused })
              }
            >
              {data.trial.paused
                ? "Resume submissions and queued work"
                : "Pause submissions and queued work"}
            </button>
          </section>
          <section className="content-panel">
            <h2>Accounts & allowance requests</h2>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Account</th>
                    <th>Usage</th>
                    <th>Access</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.accounts.map((user) => (
                    <tr key={user.account_id}>
                      <td>
                        <code>{user.account_id}</code>
                        {user.requested && (
                          <p>Additional allowance requested</p>
                        )}
                      </td>
                      <td>
                        {user.used} / {user.run_limit}
                      </td>
                      <td>{user.suspended ? "Suspended" : "Active"}</td>
                      <td>
                        <button
                          className="text-button"
                          disabled={busy}
                          onClick={() =>
                            update({
                              action: "account",
                              account_id: user.account_id,
                              run_limit: Math.min(100, user.run_limit + 3),
                              suspended: user.suspended,
                            })
                          }
                        >
                          Grant 3 runs
                        </button>
                        <button
                          className="text-button"
                          disabled={busy}
                          onClick={() =>
                            update({
                              action: "account",
                              account_id: user.account_id,
                              run_limit: user.run_limit,
                              suspended: !user.suspended,
                            })
                          }
                        >
                          {user.suspended ? "Restore access" : "Suspend"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="content-panel">
            <h2>Recent job health</h2>
            <div className="activity-log">
              <ol>
                {data.jobs.map((job) => (
                  <li key={job.investigation_id}>
                    <code>{job.investigation_id}</code>
                    <span>{job.status}</span>
                    <time>{formatDate(job.updated_at)}</time>
                  </li>
                ))}
              </ol>
            </div>
          </section>
        </>
      )}
    </>
  );
}
