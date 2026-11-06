"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isReport, formatDate } from "@/lib/reports";
import { reportMarkdown } from "@/lib/export-report";
export function InvestigationActions({
  id,
  status,
  result,
  events,
  cancelRequested,
  shared,
  reload,
}: {
  id: string;
  status: string;
  result: unknown;
  events: { message: string; created_at: string }[];
  cancelRequested: boolean;
  shared: boolean;
  reload: () => void;
}) {
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [sharePreview, setSharePreview] = useState(false),
    [shareUrl, setShareUrl] = useState("");
  const router = useRouter();
  const [clock,setClock]=useState(()=>Date.now());
  useEffect(()=>{if(!["queued","running"].includes(status))return;const timer=setInterval(()=>setClock(Date.now()),1000);return ()=>clearInterval(timer);},[status]);
  async function act(action: string) {
    setBusy(true);
    setMessage("");
    try {
      const r = await fetch(`/api/operator/investigations/${id}/${action}`, {
        method: "POST",
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error);
      if (action === "share") {
        setShareUrl(`${location.origin}/shared/${data.token}`);
        setSharePreview(false);
      }
      if (action === "revoke") setShareUrl("");
      if (action === "delete") {
        router.push("/operator");
        return;
      }
      setMessage(
        action === "cancel"
          ? "Cancellation requested. Cleanup finishes before the job stops."
          : action === "revoke"
            ? "Sharing link revoked."
            : "Sharing link created.",
      );
      reload();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Action failed. Try again.");
    } finally {
      setBusy(false);
    }
  }
  async function copy() {
    try {
      if (isReport(result)) {
        await navigator.clipboard.writeText(reportMarkdown(result));
        setMessage("Engineering ticket copied.");
      }
    } catch {
      setMessage("Clipboard access failed. Download Markdown instead.");
    }
  }
  const active = ["queued", "running"].includes(status);
  return (
    <section className="investigation-utilities">
      {events.length > 0 && <p className="elapsed-time">{["queued","running"].includes(status) ? `Elapsed since acceptance: ${Math.max(0,Math.floor((clock-new Date(events[0].created_at).getTime())/1000))}s` : "Investigation activity retained below."}</p>}
      <div className="report-actions">
        {active ? (
          <button
            className="subtle-button"
            disabled={busy || cancelRequested}
            onClick={() => act("cancel")}
          >
            {cancelRequested ? "Cancellation pending" : "Cancel investigation"}
          </button>
        ) : (
          <button
            className="text-button"
            disabled={busy}
            onClick={() => {
              if (
                confirm(
                  "Delete this private report and revoke its sharing link? This does not restore investigation allowance.",
                )
              )
                void act("delete");
            }}
          >
            Delete report
          </button>
        )}
        {status === "completed" && isReport(result) && (
          <>
            <a
              className="subtle-button"
              href={`/api/operator/investigations/${id}/markdown`}
            >
              Download Markdown
            </a>
            <a
              className="subtle-button"
              href={`/api/operator/investigations/${id}/pdf`}
            >
              Download PDF
            </a>
            <button className="subtle-button" onClick={copy}>
              Copy engineering ticket
            </button>
            <button
              className="subtle-button"
              onClick={() => setSharePreview(!sharePreview)}
            >
              Share report
            </button>
            {shared && (
              <button
                className="text-button"
                disabled={busy}
                onClick={() => act("revoke")}
              >
                Revoke sharing link
              </button>
            )}
          </>
        )}
      </div>
      {sharePreview && (
        <div className="share-preview">
          <h2>Review before sharing</h2>
          <p>
            Anyone with the link can read the entire report shown above,
            including its claim, payloads, response bodies, source hash and any
            source snippets. Your source archive and account details are
            excluded. Creating a new link revokes the previous one.
          </p>
          <details>
            <summary>Preview the exact report data</summary>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </details>
          <button
            className="button primary-button"
            disabled={busy}
            onClick={() => act("share")}
          >
            Create sharing link
          </button>
        </div>
      )}
      {shareUrl && (
        <label className="share-link">
          Sharing link
          <input readOnly value={shareUrl} onFocus={(e) => e.target.select()} />
        </label>
      )}
      {message && <p role="status">{message}</p>}
      <details className="activity-log" open={active}>
        <summary>Investigation activity · {events.length} events</summary>
        {events.length ? (
          <ol>
            {events.map((event, i) => (
              <li key={i}>
                <time>{formatDate(event.created_at)}</time>
                <span>{event.message}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p>No worker activity has been recorded yet.</p>
        )}
      </details>
    </section>
  );
}
