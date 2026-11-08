"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useRef, useEffect } from "react";
import {
  ArrowUpRight,
  ArrowLeft,
  Files,
  BookOpen,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  Shield,
  X,
} from "lucide-react";
import { ThemeToggle } from "./account-controls";
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
  const [hasSession, setHasSession] = useState(operator);
  const [isLocal, setIsLocal] = useState(local);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    fetch("/api/session")
      .then((r) => r.json())
      .then((data) => {
        if (data.authenticated) {
          setHasSession(true);
          if (data.account?.local) setIsLocal(true);
          if (data.account?.admin) setIsAdmin(true);
        }
      })
      .catch(() => {});
  }, []);

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

  const isOperator = operator || hasSession;
  const isLocalMode = local || isLocal;

  const links = [
    { href: "/operator", title: "My investigations", icon: LayoutDashboard },
    {
      href: "/operator/investigations/new",
      title: "New investigation",
      icon: Plus,
    },
    { href: "/investigations", title: "Example investigations", icon: Files },
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

  const isInsidePublicSection = path.startsWith("/investigations") || path === "/guide";

  function renderBreadcrumbs() {
    if (path === "/operator") {
      return (
        <nav aria-label="Breadcrumb" className="topbar-breadcrumb">
          <span className="breadcrumb-current">My investigations</span>
        </nav>
      );
    }
    if (path === "/operator/investigations/new") {
      return (
        <nav aria-label="Breadcrumb" className="topbar-breadcrumb">
          <Link href="/operator" className="breadcrumb-link">Investigations</Link>
          <span className="breadcrumb-sep">/</span>
          <span className="breadcrumb-current">New investigation</span>
        </nav>
      );
    }
    if (path.startsWith("/operator/investigations/")) {
      const invId = path.replace("/operator/investigations/", "");
      return (
        <nav aria-label="Breadcrumb" className="topbar-breadcrumb">
          <Link href="/operator" className="breadcrumb-link">Investigations</Link>
          <span className="breadcrumb-sep">/</span>
          <span className="breadcrumb-current breadcrumb-mono">{invId}</span>
        </nav>
      );
    }
    if (path === "/operator/admin") {
      return (
        <nav aria-label="Breadcrumb" className="topbar-breadcrumb">
          <Link href="/operator" className="breadcrumb-link">Workspace</Link>
          <span className="breadcrumb-sep">/</span>
          <span className="breadcrumb-current">Administration</span>
        </nav>
      );
    }
    if (path === "/investigations") {
      return (
        <nav aria-label="Breadcrumb" className="topbar-breadcrumb">
          <span className="breadcrumb-current">Example investigations</span>
        </nav>
      );
    }
    if (path.startsWith("/investigations/")) {
      const exampleId = path.replace("/investigations/", "");
      return (
        <nav aria-label="Breadcrumb" className="topbar-breadcrumb">
          <Link href="/investigations" className="breadcrumb-link">Examples</Link>
          <span className="breadcrumb-sep">/</span>
          <span className="breadcrumb-current breadcrumb-mono">{exampleId}</span>
        </nav>
      );
    }
    if (path === "/guide") {
      return (
        <nav aria-label="Breadcrumb" className="topbar-breadcrumb">
          <span className="breadcrumb-current">Using Cairn</span>
        </nav>
      );
    }
    if (path === "/privacy") {
      return (
        <nav aria-label="Breadcrumb" className="topbar-breadcrumb">
          <span className="breadcrumb-current">Privacy & Security</span>
        </nav>
      );
    }
    return (
      <nav aria-label="Breadcrumb" className="topbar-breadcrumb">
        <span className="breadcrumb-current">{isOperator ? "Workspace" : "Evidence"}</span>
      </nav>
    );
  }

  return (
    <div className="workspace">
      <a className="skip-link" href="#workspace-main">
        Skip to content
      </a>
      <aside className="workspace-sidebar">
        <div className="workspace-brand">
          <Link
            href="/"
            aria-label="Cairn home"
            onClick={() => {
              window.scrollTo({ top: 0, left: 0, behavior: "instant" });
            }}
          >
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
            {isAdmin && (
              <Link className="sidebar-utility" href="/operator/admin">
                <Shield size={16} />
                Administration
              </Link>
            )}
            {isOperator && !isLocalMode ? (
              <button className="sidebar-utility" onClick={logout}>
                <LogOut size={16} />
                Sign out
              </button>
            ) : !isOperator ? (
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
          {renderBreadcrumbs()}
          <div className="topbar-right-group">
            {isInsidePublicSection && (
              <Link href="/operator" className="topbar-back-link">
                <ArrowLeft size={13} /> My investigations
              </Link>
            )}
            {isAdmin && path !== "/operator/admin" && (
              <Link href="/operator/admin" className="topbar-admin-btn">
                <Shield size={12} /> Admin
              </Link>
            )}
          </div>
        </header>
        <main id="workspace-main" className="workspace-main">
          {children}
        </main>
        <footer className="workspace-footer">
          <span>Cairn · Automated Security Verification</span>
          <Link
            href="/"
            onClick={() => {
              window.scrollTo({ top: 0, left: 0, behavior: "instant" });
            }}
          >
            Back to overview <ArrowUpRight size={13} />
          </Link>
        </footer>
      </div>
    </div>
  );
}
