"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useRef } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  FileArchive,
  Upload,
} from "lucide-react";
const exampleReport =
  "Investigate command injection in the Northstar Diagnostics API. The GET /api/v1/diagnostics/resolve endpoint accepts a host parameter which may be interpolated into a shell command. Inspect the supplied source, identify the actual route, and test whether harmless marker evidence can reproduce the claim. Distinguish a negative result from a setup failure.";
export function NewInvestigation() {
  const router = useRouter();
  const [sourceType, setSourceType] = useState("upload");
  const [githubUrl, setGithubUrl] = useState("");
  const [githubRef, setGithubRef] = useState("");
  const submissionKey = useRef("");
  const [step, setStep] = useState(0);
  const [report, setReport] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [runtime, setRuntime] = useState("python");
  const [subject, setSubject] = useState("http_app");
  const [argv, setArgv] = useState('["python3", "app.py"]');
  const [port, setPort] = useState(5000);
  const [directory, setDirectory] = useState(".");
  const [mode, setMode] = useState("controlled_network");
  const [scripts, setScripts] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [uncertain, setUncertain] = useState(false);
  function manifest() {
    if (
      subject === "http_app" &&
      (!Number.isInteger(port) || port < 1 || port > 65535)
    )
      throw new Error("HTTP port must be an integer from 1 to 65535.");
    const args: unknown = JSON.parse(argv);
    if (
      !Array.isArray(args) ||
      !args.length ||
      args.length > 32 ||
      args.some(
        (x) =>
          typeof x !== "string" || !x || x.length > 1024 || x.includes("\0"),
      )
    )
      throw new Error(
        "Arguments must be a JSON array of 1–32 nonempty strings.",
      );
    if (
      directory.startsWith("/") ||
      directory.includes("\\") ||
      directory.split("/").includes("..")
    )
      throw new Error("Use a relative working directory inside the archive.");
    return {
      subject_type: subject,
      runtime,
      [subject === "http_app" ? "start_argv" : "test_argv"]: args,
      ...(subject === "http_app" ? { port } : {}),
      working_directory: directory || ".",
      dependency_mode: mode,
      allow_network_during_install: mode === "controlled_network",
      allow_install_scripts: scripts,
    };
  }
  function next() {
    setError("");
    try {
      if (
        step === 0 &&
        ((sourceType === "upload" &&
          (!file ||
            !/\.(tar\.gz|tgz)$/i.test(file.name) ||
            file.size === 0 ||
            file.size > 10 * 1024 * 1024)) ||
          (sourceType === "github" &&
            !/^https:\/\/github\.com\/[^/]+\/[^/]+\/?$/.test(githubUrl)) ||
          !report.trim() ||
          report.length > 20_000)
      )
        throw new Error(
          "Choose a nonempty source archive up to 10 MiB and enter a report.",
        );
      if (step === 1) manifest();
      setStep(step + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Check the required fields.");
    }
  }
  async function example() {
    setError("");
    setBusy(true);
    try {
      const r = await fetch("/examples/northstar.tar.gz");
      if (!r.ok) throw new Error();
      setSourceType("upload");
      setFile(new File([await r.blob()], "northstar.tar.gz"));
      setReport(exampleReport);
      setRuntime("python");
      setSubject("http_app");
      setDirectory(".");
      setMode("offline");

      setArgv('["python3", "app.py"]');
      setPort(5002);
    } catch {
      setError(
        "The example archive could not be loaded. Choose your own source archive.",
      );
    } finally { setBusy(false); }
  }
  async function submit() {
    if (busy || !confirmed || (sourceType === "upload" && !file) || uncertain)
      return;
    setError("");
    setBusy(true);
    try {
      const form = new FormData();
      if (sourceType === "upload" && file) form.set("source", file);
      else {
        form.set("github_url", githubUrl);
        form.set("github_ref", githubRef);
      }
      if (!submissionKey.current) submissionKey.current = crypto.randomUUID();
      form.set("report", report);
      form.set("manifest", JSON.stringify(manifest()));
      const response = await fetch("/api/operator/investigations", {
        method: "POST",
        headers: { "Idempotency-Key": submissionKey.current },
        body: form,
      });
      const data = await response.json().catch(() => {
        setUncertain(true);
        throw new Error(
          "The submission outcome is unknown. Check investigations before submitting again.",
        );
      });
      if (!response.ok) {
        if (
          response.status >= 500 ||
          data.error?.includes("outcome is unknown")
        )
          setUncertain(true);
        throw new Error(
          data.error || "The investigation could not be submitted.",
        );
      }
      if (!/^inv-[a-zA-Z0-9-]{1,100}$/.test(data.investigation_id)) {
        setUncertain(true);
        throw new Error(
          "The service returned an unexpected acknowledgment. Check the investigation list before submitting again.",
        );
      }
      router.push(`/operator/investigations/${data.investigation_id}`);
    } catch (e) {
      if (e instanceof TypeError) setUncertain(true);
      setError(
        e instanceof Error
          ? e.message
          : "Submission interrupted. Check the investigation list.",
      );
      setBusy(false);
    }
  }
  return (
    <>
      <Link className="back-link" href="/operator">
        <ArrowLeft size={15} />
        Investigations
      </Link>
      <div className="page-heading">
        <div>
          <h1>Start with a claim.</h1>
          <p>Supply the source and tell Cairn what to investigate.</p>
        </div>
      </div>
      <ol className="form-progress">
        {["Report & source", "Runtime", "Review & submit"].map(
          (label, index) => (
            <li
              key={label}
              className={
                index === step ? "current" : index < step ? "done" : ""
              }
            >
              <span>{index < step ? <Check size={14} /> : index + 1}</span>
              {label}
            </li>
          ),
        )}
      </ol>
      <div className="submission-layout">
        <div className="submission-form">
          {step === 0 && (
            <>
              <h2>What needs to be verified?</h2>
              <label htmlFor="claim">Vulnerability report</label>
              <textarea
                id="claim"
                rows={9}
                maxLength={20_000}
                value={report}
                onChange={(e) => setReport(e.target.value)}
                placeholder="Describe the suspected behavior, affected route or package, and the conditions needed to reproduce it."
              />
              <div className="field-hint">
                {report.length.toLocaleString()} / 20,000 characters
              </div>
              <label htmlFor="source-type">Source location</label>
              <select
                id="source-type"
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
              >
                <option value="upload">Upload archive</option>
                <option value="github">Public GitHub repository</option>
              </select>
              {sourceType === "github" ? (
                <div className="github-fields">
                  <label htmlFor="github-url">Public repository URL</label>
                  <input
                    id="github-url"
                    type="url"
                    value={githubUrl}
                    onChange={(e) => setGithubUrl(e.target.value)}
                    placeholder="https://github.com/owner/repository"
                  />
                  <label htmlFor="github-ref">Branch, tag, or commit · optional</label>
                  <input
                    id="github-ref"
                    placeholder="Default branch"
                    value={githubRef}
                    onChange={(e) => setGithubRef(e.target.value)}
                    maxLength={200}
                  />
                  <p className="field-hint">
                    Import limit: 10 MiB compressed. Use a commit for
                    reproducible source. Repository access does not grant
                    permission to investigate it.
                  </p>
                </div>
              ) : (
                <>
                  <label htmlFor="source">Source archive</label>
                  <div className="file-drop">
                    <Upload size={26} />
                    <strong>
                      {file ? file.name : "Choose a .tar.gz source archive"}
                    </strong>
                    <span>
                      {file
                        ? `${(file.size / 1024).toFixed(1)} KiB`
                        : "Maximum 10 MiB. Do not include credentials or private keys."}
                    </span>
                    <input
                      id="source"
                      type="file"
                      accept=".tar.gz,.tgz,application/gzip"
                      onChange={(e) => {
                        setFile(e.target.files?.[0] || null);
                        setError("");
                      }}
                    />
                  </div>
                </>
              )}
              <button type="button" className="text-button" disabled={busy} onClick={example}>
                Use the owned Northstar example
              </button>
            </>
          )}
          {step === 1 && (
            <>
              <h2>How does the subject run?</h2>
              <div className="field-grid">
                <label>
                  Runtime
                  <select
                    value={runtime}
                    onChange={(e) => setRuntime(e.target.value)}
                  >
                    <option value="python">Python</option>
                    <option value="node">Node.js</option>
                    <option value="go">Go</option>
                  </select>
                </label>
                <label>
                  Subject type
                  <select
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                  >
                    <option value="http_app">HTTP application</option>
                    <option value="package_harness">
                      Package test harness
                    </option>
                  </select>
                </label>
              </div>
              <label htmlFor="argv">
                {subject === "http_app" ? "Startup" : "Test"} arguments · JSON
                array
              </label>
              <textarea
                id="argv"
                className="code-input"
                rows={3}
                value={argv}
                onChange={(e) => setArgv(e.target.value)}
              />
              <p className="field-hint">
                Arguments are passed separately. The HTTP port must match the port your application actually listens on (Flask defaults to 5000). Choose a runtime available in your sandbox image.
              </p>
              <div className="field-grid">
                {subject === "http_app" && (
                  <label>
                    HTTP port
                    <input
                      type="number"
                      min={1}
                      max={65535}
                      value={port}
                      onChange={(e) => setPort(Number(e.target.value))}
                    />
                  </label>
                )}
                <label>
                  Working directory
                  <input
                    value={directory}
                    onChange={(e) => setDirectory(e.target.value)}
                    maxLength={200}
                  />
                </label>
              </div>
              <label>
                Dependencies
                <select value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="controlled_network">Install from package registries inside Celesto</option>
                  <option value="offline">
                    Offline · no dependency downloads
                  </option>
                  <option value="prebuilt">Prebuilt image</option>
                </select>
              </label>
              <label><input type="checkbox" checked={scripts} onChange={(e) => setScripts(e.target.checked)} /> Allow package installation scripts inside the sandbox</label>
              <p className="field-hint">
                Python installs requirements.txt (including Flask); Node installs package.json dependencies; Go downloads go.mod modules. Networking stays enabled for this sandbox in download mode.
              </p>
            </>
          )}
          {step === 2 && (
            <>
              <h2>Ready for investigation?</h2>
              <div className="review-source">
                <FileArchive size={24} />
                <div>
                  <strong>
                    {sourceType === "github" ? githubUrl : file?.name}
                  </strong>
                  <span>
                    {sourceType === "github"
                      ? githubRef
                      : `${((file?.size || 0) / 1024).toFixed(1)} KiB`}
                  </span>
                </div>
              </div>
              <h3>Claim</h3>
              <p className="readable-pre">{report}</p>
              <details className="manifest-review">
                <summary>Review the runtime manifest</summary>
                <pre>{JSON.stringify(manifest(), null, 2)}</pre>
              </details>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                I own this source or have permission to investigate it.
              </label>
              <div className="notice">
                This uses one investigation from your allowance. Source archives
                are removed after execution; reports remain available for 30
                days.
              </div>
            </>
          )}
          {error && (
            <div className="form-error" role="alert">
              {error}
              {uncertain && (
                <>
                  <p>
                    Do not submit again until you have checked whether the job
                    was accepted.
                  </p>
                  <Link href="/operator">Check investigations</Link>
                </>
              )}
            </div>
          )}
          <div className="form-actions">
            {step > 0 && (
              <button
                className="subtle-button"
                disabled={busy || uncertain}
                onClick={() => {
                  setStep(step - 1);
                  setError("");
                }}
              >
                Back
              </button>
            )}
            {step < 2 ? (
              <button className="button primary-button" disabled={busy} onClick={next}>
                Continue
                <ArrowRight size={17} />
              </button>
            ) : (
              <button
                className="button primary-button"
                disabled={!confirmed || busy || uncertain}
                onClick={submit}
              >
                {busy ? "Submitting once…" : "Start investigation"}
                <ArrowRight size={17} />
              </button>
            )}
          </div>
        </div>
        <aside className="submission-aside">
          <h2>Evidence starts here.</h2>
          <p>
            A useful report describes one testable behavior. Include the
            affected path, input, and expected result.
          </p>
          <ul>
            <li>Source runs inside a Celesto guest.</li>
            <li>Positive findings need an independent marker recheck.</li>
            <li>A negative result is limited to tested conditions.</li>
          </ul>
          <Link href="/investigations/northstar-vulnerable">
            See a completed investigation <ArrowRight size={15} />
          </Link>
        </aside>
      </div>
    </>
  );
}
