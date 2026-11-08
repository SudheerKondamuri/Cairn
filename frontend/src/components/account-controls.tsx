"use client";
import Link from "next/link";
import { useState, useEffect } from "react";
import { Moon, Sun } from "lucide-react";
import { useRemote } from "@/lib/use-remote";
import type { Account } from "@/lib/auth";
export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const saved = localStorage.getItem("cairn-theme");
    const enabled = saved
      ? saved === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = enabled ? "dark" : "light";
    setDark(enabled);
  }, []);
  function toggle() {
    const next = !dark;
    setDark(next);
    localStorage.setItem("cairn-theme", next ? "dark" : "light");
    document.documentElement.dataset.theme = next ? "dark" : "light";
  }
  return (
    <button
      className="sidebar-utility"
      onClick={toggle}
      aria-label={dark ? "Use light theme" : "Use dark theme"}
    >
      {dark ? <Sun size={16} /> : <Moon size={16} />}{" "}
      {dark ? "Light theme" : "Dark theme"}
    </button>
  );
}
export function AccountControls() {
  const { data, error, reload } = useRemote<Account>("/api/operator/me", 15000);
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const isLocal = !!(data?.local || data?.allowance?.unlimited);
  async function request() {
    setBusy(true);
    try {
      const r = await fetch("/api/operator/allowance-request", {
        method: "POST",
      });
      if (!r.ok) throw new Error();
      setMessage("Request sent. Your existing reports remain available.");
      reload();
    } catch {
      setMessage("Request could not be sent. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="allowance-strip" aria-label={isLocal ? "Workspace status" : "Trial allowance"}>
      <span className="allowance-label">{isLocal ? "Workspace" : "Investigation allowance"}</span>
      <div>
        <strong>
          {!data
            ? "Checking status…"
            : isLocal
              ? "Unlimited investigations"
              : typeof data.allowance.remaining === "number" && typeof data.allowance.limit === "number"
                ? `${data.allowance.remaining} of ${data.allowance.limit} investigations available`
                : "Unlimited investigations"}
        </strong>
        {data && !isLocal && typeof data.allowance.limit === "number" && typeof data.allowance.remaining === "number" && (
          <div className="allowance-meter" role="meter" aria-label="Investigations remaining" aria-valuemin={0} aria-valuemax={data.allowance.limit} aria-valuenow={data.allowance.remaining}>
            <span style={{width:`${Math.min(100, Math.max(0, (data.allowance.remaining / Math.max(1, data.allowance.limit)) * 100))}%`}} />
          </div>
        )}
        <p>
          {isLocal
            ? "Running in local workspace with your configured Celesto and provider credentials. No run limits apply."
            : data?.allowance.paused
              ? "Live investigations are paused. Your reports remain accessible."
              : data?.allowance.trial_remaining === 0
                ? "The public trial has reached its capacity. Explore recorded cases or run Cairn locally."
                : "One allowance per live run. Examples are always open."}
        </p>
        {error && <p role="alert">{error}</p>}
      </div>
      <div className="allowance-actions">
        {data?.admin && (
          <Link className="subtle-button" href="/operator/admin">
            Administration
          </Link>
        )}
        {!isLocal && data?.allowance.remaining === 0 && (
          <>
            <button
              className="subtle-button"
              disabled={busy || data.allowance.request_pending}
              onClick={request}
            >
              {data.allowance.request_pending
                ? "Request pending"
                : "Request more runs"}
            </button>
            <a
              href="https://github.com/SudheerKondamuri/Cairn#setup"
              className="text-button"
            >
              Run locally
            </a>
          </>
        )}
        {message && <p role="status">{message}</p>}
      </div>
    </section>
  );
}
