"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { Wordmark } from "./brand";

const links = [
  { href: "/investigations", label: "Examples" },
  { href: "/guide", label: "Guide" },
  { href: "#how-it-works", label: "How it works" },
  {
    href: "https://github.com/SudheerKondamuri/Cairn",
    label: "Source",
    external: true,
  },
];

export function Navigation() {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const nav = useRef<HTMLElement>(null);

  useEffect(() => {
    // When navigating to the landing page without a specific anchor, ensure fresh top start
    if (!window.location.hash) {
      window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    function close(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    }
    function outside(event: PointerEvent) {
      if (!nav.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("keydown", close);
    document.addEventListener("pointerdown", outside);
    return () => {
      document.removeEventListener("keydown", close);
      document.removeEventListener("pointerdown", outside);
    };
  }, [open]);

  return (
    <header className="site-header" ref={nav}>
      <a
        href="#top"
        className="brand-link"
        aria-label="Cairn home"
        onClick={() => setOpen(false)}
      >
        <Wordmark />
      </a>
      <nav className="desktop-nav" aria-label="Main navigation">
        {links.map((link) => (
          <a
            key={link.href}
            href={link.href}
            {...(link.external
              ? { target: "_blank", rel: "noopener noreferrer" }
              : {})}
          >
            {link.label}
            {link.external && <ArrowUpRight size={14} />}
          </a>
        ))}
      </nav>
      <a className="header-action" href="/operator">
        Open workspace <ArrowUpRight size={16} />
      </a>
      <button
        className="menu-toggle"
        ref={button}
        aria-label={open ? "Close navigation" : "Open navigation"}
        aria-expanded={open}
        aria-controls="mobile-navigation"
        onClick={() => setOpen(!open)}
      >
        {open ? <X /> : <Menu />}
      </button>
      <nav
        className="mobile-nav"
        id="mobile-navigation"
        aria-label="Mobile navigation"
        hidden={!open}
      >
        {links.map((link) => (
          <a
            key={link.href}
            href={link.href}
            onClick={() => setOpen(false)}
            {...(link.external
              ? { target: "_blank", rel: "noopener noreferrer" }
              : {})}
          >
            {link.label}
            <ArrowUpRight size={18} />
          </a>
        ))}
        <a href="/operator" onClick={() => setOpen(false)}>
          Open workspace <ArrowUpRight size={18} />
        </a>
      </nav>
    </header>
  );
}
