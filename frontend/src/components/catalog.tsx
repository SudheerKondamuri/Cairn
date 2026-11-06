"use client";
import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, Search } from "lucide-react";
import { published, verdictLabel } from "@/lib/reports";
export function Catalog() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const items = published.filter(
    (item) =>
      `${item.title} ${item.version} ${item.description}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (filter === "all" || item.report.verdict === filter),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="breadcrumb">Published workspace</p>
          <h1>Investigations</h1>
          <p>Follow the claim. Inspect the requests. Question the outcome.</p>
        </div>
        <span className="record-count">{published.length} published cases</span>
      </div>
      <div className="catalog-feature">
        <div className="feature-glyph" aria-hidden="true">
          N
        </div>
        <div>
          <h2>One application. Two source versions.</h2>
          <p>
            Northstar Diagnostics makes the difference between reproduced
            behavior and a negative result inspectable.
          </p>
        </div>
        <span className="feature-date">
          Recorded
          <br />
          24 Oct 2026
        </span>
      </div>
      <div className="filter-bar">
        <label className="search-field">
          <Search size={17} />
          <span className="sr-only">Search published investigations</span>
          <input
            placeholder="Search investigations…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <label>
          <span className="sr-only">Filter verdict</span>
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All verdicts</option>
            <option value="verified">Verified vulnerability</option>
            <option value="not_reproduced">Not reproduced</option>
          </select>
        </label>
      </div>
      <div className="case-list">
        {items.map((item) => (
          <Link
            className="case-row"
            href={`/investigations/${item.slug}`}
            key={item.slug}
          >
            <div className="case-row-icon">
              N<span>{item.version}</span>
            </div>
            <div className="case-row-main">
              <h2>{item.title}</h2>
              <p>{item.description}</p>
              <span>
                Python · HTTP application ·{" "}
                {item.report.evidence.attempts.length} recorded requests
              </span>
            </div>
            <div className="case-row-end">
              <span className={`status-badge ${item.report.verdict}`}>
                {verdictLabel(item.report.verdict)}
              </span>
              <ArrowUpRight size={22} />
            </div>
          </Link>
        ))}
      </div>
      {!items.length && (
        <div className="empty-state">
          <Search size={30} />
          <h2>No matching investigations</h2>
          <p>Try another search or show all verdicts.</p>
          <button
            className="subtle-button"
            onClick={() => {
              setQuery("");
              setFilter("all");
            }}
          >
            Clear filters
          </button>
        </div>
      )}
      <p className="workspace-disclaimer">
        These are selected recordings, not live jobs. A negative finding is
        limited to the tested source and conditions.
      </p>
    </>
  );
}
