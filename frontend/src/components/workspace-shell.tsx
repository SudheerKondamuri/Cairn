"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useRef, useEffect } from "react";
import {
  ArrowUpRight,
  Files,
  BookOpen,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  X,
} from "lucide-react";
import { AccountControls, ThemeToggle } from "./account-controls";
import { Wordmark } from "./brand";

export function WorkspaceShell({
  children,
  operator = false,
  local = false,
}: {
  children: React.ReactNode;
  operator?: boolean;
  local?: boolean;
}) {
  const path = usePathname();
  const router = useRouter();
  const menu = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        menu.current?.focus();
      }
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [open]);
  const links = operator
    ? [
        { href: "/operator", title: "Investigations", icon: LayoutDashboard },
        {
          href: "/operator/investigations/new",
          title: "New investigation",
          icon: Plus,
        },
        { href: "/investigations", title: "Example investigations", icon: Files },
        { href: "/guide", title: "Using Cairn", icon: BookOpen },
      ]
    : [
        { href: "/investigations", title: "Investigations", icon: Files },
        { href: "/guide", title: "Using Cairn", icon: BookOpen },
      ];
  async function logout() {
    try {
      const r = await fetch("/api/session", { method: "DELETE" });
      if (!r.ok) throw new Error();
      router.replace("/operator/sign-in");
      router.refresh();
    } catch {
      setError("Sign-out failed. Please try again.");
    }
  }
  return (
    <div className="workspace">
      <a className="skip-link" href="#workspace-main">
        Skip to content
      </a>
      <aside className="workspace-sidebar">
        <div className="workspace-brand">
          <Link href="/" aria-label="Cairn home">
            <Wordmark />
          </Link>
          <button
            ref={menu}
            className="workspace-menu icon-button"
            aria-label={
              open ? "Close workspace navigation" : "Open workspace navigation"
            }
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            {open ? <X /> : <Menu />}
          </button>
        </div>
        <div className={`workspace-navigation ${open ? "is-open" : ""}`}>
          <div className="workspace-mode">
            <span className={operator ? "mode-dot operator-dot" : "mode-dot"} />
            {operator ? "Your workspace" : "Public evidence"}
          </div>
          <nav aria-label="Workspace navigation">
            {links.map(({ href, title, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                aria-current={path === href ? "page" : undefined}
                onClick={() => setOpen(false)}
              >
                <Icon size={18} />
                {title}
              </Link>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <ThemeToggle />
            <p>
              {operator
                ? "Private by default. Execution stays inside Celesto."
                : "Real recorded investigations. Open for inspection."}
            </p>
            {operator && !local ? (
              <button className="sidebar-utility" onClick={logout}>
                <LogOut size={16} />
                Sign out
              </button>
            ) : !operator ? (
              <Link className="sidebar-utility" href="/operator">
                <ArrowUpRight size={16} />
                Sign in
              </Link>
            ) : null}
            <a
              className="sidebar-utility"
              href="https://github.com/SudheerKondamuri/Cairn"
              target="_blank"
              rel="noopener noreferrer"
            >
              Source on GitHub <ArrowUpRight size={14} />
            </a>
            {error && <p role="alert">{error}</p>}
          </div>
        </div>
      </aside>
      <div className="workspace-body">
        <header className="workspace-topbar">
          <span>{operator ? "Private workspace" : "The evidence room"}</span>
          <span className="workspace-top-note">
            {local ? "Local workspace" : operator ? "Private account" : "Published recordings"}
            <span className="small-cairn" />
          </span>
        </header>
        <main id="workspace-main" className="workspace-main">
          {operator && <AccountControls />}
          {children}
        </main>
        <footer className="workspace-footer">
          <span>Cairn. A finding with a foundation.</span>
          <Link href="/">
            Back to the introduction <ArrowUpRight size={13} />
          </Link>
        </footer>
      </div>
    </div>
  );
}
