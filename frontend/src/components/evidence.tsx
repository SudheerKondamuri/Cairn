"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import {
  ArrowDownToLine,
  Check,
  Copy,
  FileCode2,
  Minus,
  MoveUpRight,
} from "lucide-react";

export type CaseEvidence = {
  key: "vulnerable" | "patched";
  version: string;
  verdict: string;
  hash: string;
  attempts: number;
  marker: boolean;
  independent: boolean | null;
  payload: string;
  route: string;
  source: string[];
  download: string;
};

export function Evidence({ cases }: { cases: CaseEvidence[] }) {
  const [selected, setSelected] = useState(0);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const [rawOpen, setRawOpen] = useState(false);
  const controls = useRef<(HTMLButtonElement | null)[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const id = useId();
  const current = cases[selected];
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  function select(index: number) {
    setSelected(index);
    setCopied(false);
    setCopyError(false);
  }
  function navigate(event: KeyboardEvent<HTMLButtonElement>) {
    let index = selected;
    if (event.key === "ArrowRight" || event.key === "ArrowLeft")
      index = 1 - selected;
    else if (event.key === "Home") index = 0;
    else if (event.key === "End") index = 1;
    else return;
    event.preventDefault();
    select(index);
    controls.current[index]?.focus();
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(current.payload);
      setCopied(true);
      setCopyError(false);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyError(true);
    }
  }

  return (
    <div className="evidence-shell">
      <div className="evidence-toolbar">
        <div className="case-identity">
          <span className="case-symbol">N</span>
          <div>
            <strong>Northstar Diagnostics</strong>
            <span>Owned demo application · 24 October 2026</span>
          </div>
        </div>
        <div
          className="case-tabs"
          role="tablist"
          aria-label="Compare recorded source versions"
        >
          {cases.map((item, index) => (
            <button
              key={item.key}
              id={`${id}-tab-${index}`}
              role="tab"
              aria-selected={selected === index}
              aria-controls={`${id}-panel`}
              tabIndex={selected === index ? 0 : -1}
              ref={(element) => {
                controls.current[index] = element;
              }}
              onClick={() => select(index)}
              onKeyDown={navigate}
            >
              {item.key === "vulnerable" ? "Vulnerable" : "Patched"}
              <span className="tab-dot" />
            </button>
          ))}
        </div>
      </div>
      <div
        id={`${id}-panel`}
        role="tabpanel"
        aria-labelledby={`${id}-tab-${selected}`}
        tabIndex={0}
      >
        <div className="evidence-main">
          <div className="source-pane">
            <div className="source-heading">
              <span>
                <FileCode2 size={16} /> app.py
              </span>
              <span>
                Python{" "}
                <span className="source-version">v{current.version}</span>
              </span>
            </div>
            <pre
              className="source-code"
              aria-label={`${current.key} source excerpt`}
            >
              <code>
                {current.source.map((line, index) => (
                  <span
                    className={`code-line ${line.includes("shell=") ? "code-focus" : ""}`}
                    key={`${current.key}-${index}`}
                  >
                    <span className="line-number" aria-hidden="true">
                      {index + (selected === 0 ? 29 : 22)}
                    </span>
                    <span>
                      {line.includes("shell=") ? (
                        <>
                          <span className="code-property"> shell=</span>
                          <span
                            className={
                              selected === 0 ? "code-unsafe" : "code-safe"
                            }
                          >
                            {selected === 0 ? "True" : "False"}
                          </span>
                          ,
                        </>
                      ) : (
                        line
                      )}
                    </span>
                  </span>
                ))}
              </code>
            </pre>
            <div className="request-proof">
              <div className="request-route">
                <span>GET</span>
                <code>{current.route}</code>
              </div>
              <span className="request-label">The same injected input</span>
              <div className="payload">
                <code>{current.payload}</code>
                <button
                  className="copy-button"
                  onClick={copy}
                  aria-label={copied ? "Payload copied" : "Copy payload"}
                >
                  {copied ? <Check size={16} /> : <Copy size={16} />}
                </button>
              </div>
              <span
                className={copyError ? "copy-error" : "sr-only"}
                role="status"
              >
                {copied
                  ? "Payload copied."
                  : copyError
                    ? "Copy unavailable. Select and copy the payload text."
                    : ""}
              </span>
            </div>
          </div>
          <div className="result-pane" aria-live="polite" aria-atomic="true">
            <span className="result-intro">What the investigation found</span>
            <h3
              className={
                selected === 0 ? "verdict verified" : "verdict not-reproduced"
              }
            >
              {current.verdict}
            </h3>
            <p>
              {selected === 0
                ? "The input became a command. A separate request confirmed the behavior."
                : "The input stayed input. No marker was observed in this bounded investigation."}
            </p>
            <ul className="observations">
              <li>
                <span>Primary marker</span>
                <span>
                  {current.marker ? (
                    <>
                      <span className="observation-marker" /> Observed
                    </>
                  ) : (
                    <>
                      <Minus size={15} /> Not observed
                    </>
                  )}
                </span>
              </li>
              <li>
                <span>Independent recheck</span>
                <span>
                  {current.independent ? (
                    <>
                      <span className="observation-marker" /> Confirmed
                    </>
                  ) : (
                    <>
                      <Minus size={15} /> Not triggered
                    </>
                  )}
                </span>
              </li>
              <li>
                <span>Investigation attempts</span>
                <span>{current.attempts}</span>
              </li>
            </ul>
            <a className="report-link" href={current.download} download>
              Download the evidence <ArrowDownToLine size={15} />
            </a>
            <a
              className="report-link full-report-link"
              href={`/investigations/northstar-${current.key}`}
            >
              Open full investigation <MoveUpRight size={15} />
            </a>
          </div>
        </div>
        <div className="evidence-footer">
          <span>
            <span className="recorded-dot" /> Recorded evidence, inspectable
            source
          </span>
          <button
            aria-expanded={rawOpen}
            aria-controls={`${id}-provenance`}
            onClick={() => setRawOpen(!rawOpen)}
          >
            {rawOpen ? "Hide" : "View"} provenance <MoveUpRight size={13} />
          </button>
        </div>
        <div className="provenance" id={`${id}-provenance`} hidden={!rawOpen}>
          <p>
            <strong>Source SHA-256</strong>
            <code>{current.hash}</code>
          </p>
          <p>
            The report records guest deletion.{" "}
            {current.independent
              ? "The independent recheck used a fresh token and a separate controller-created request in the same guest."
              : "The investigation exhausted its bounded budget without marker evidence. This does not establish that all paths or configurations are safe."}
          </p>
        </div>
      </div>
      <p className="evidence-caption">
        Two recorded investigations of the same claim, against different source
        versions. A negative result applies to the tested conditions.
      </p>
    </div>
  );
}
