import vulnerable from "../../public/evidence/northstar-vulnerable.json";
import patched from "../../public/evidence/northstar-patched.json";

export type Attempt = {
  path: string;
  param_name: string;
  param_value: string;
  status: number | null;
  body: string;
  elapsed_ms: number;
  marker_detected: boolean;
  outcome: string;
};
export type Report = {
  investigation_id: string;
  generated_at: string;
  verdict: string;
  summary: string;
  claim: { report: string; runtime: string; subject_type: string };
  evidence: {
    attempts: Attempt[];
    source_hash: string | null;
    agent_rationale?: string | null;
    request: { path: string; param_name: string; param_value: string };
    independent_recheck: {
      fresh_token?: string;
      marker_detected: boolean;
      outcome: string;
      status?: number;
      request_constructed_by?: string;
    } | null;
  };
  lifecycle: {
    sandbox_name: string;
    sandbox_deleted: boolean;
    wall_clock_s: number;
    source_uploaded?: boolean;
    application_started?: boolean;
  };
  explanation?: { why: string[]; remediation: string[]; next_action: string };
  error?: string | null;
};
export const published = [
  {
    slug: "northstar-vulnerable",
    title: "Northstar Diagnostics",
    version: "1.4.2",
    description:
      "A host parameter crosses the boundary from data into a shell command.",
    report: vulnerable as Report,
  },
  {
    slug: "northstar-patched",
    title: "Northstar Diagnostics",
    version: "1.4.3",
    description:
      "An argument-vector implementation is investigated against the same claim.",
    report: patched as Report,
  },
];
export function verdictLabel(verdict: string) {
  return (
    (
      {
        verified: "Vulnerability verified",
        not_reproduced: "Not reproduced",
        inconclusive: "Inconclusive",
      } as Record<string, string>
    )[verdict] || "Outcome unavailable"
  );
}
export function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not recorded"
    : new Intl.DateTimeFormat("en", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "UTC",
      }).format(date) + " UTC";
}
const object = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === "object" && !Array.isArray(value);
const strings = (value: unknown) =>
  Array.isArray(value) && value.every((x) => typeof x === "string");
export function isReport(value: unknown): value is Report {
  if (!object(value)) return false;
  const { claim, evidence, lifecycle, explanation } = value;
  if (!object(claim) || !object(evidence) || !object(lifecycle)) return false;
  const recheck = evidence.independent_recheck;
  return (
    [
      value.investigation_id,
      value.generated_at,
      value.verdict,
      value.summary,
      claim.report,
      claim.runtime,
      claim.subject_type,
      lifecycle.sandbox_name,
    ].every((x) => typeof x === "string") &&
    (evidence.source_hash === null || typeof evidence.source_hash === "string") &&
    typeof lifecycle.sandbox_deleted === "boolean" &&
    typeof lifecycle.wall_clock_s === "number" &&
    Number.isFinite(lifecycle.wall_clock_s) &&
    (evidence.agent_rationale == null ||
      typeof evidence.agent_rationale === "string") &&
    Array.isArray(evidence.attempts) &&
    evidence.attempts.every(
      (a) =>
        object(a) &&
        [a.path, a.param_name, a.param_value, a.body, a.outcome].every(
          (x) => typeof x === "string",
        ) &&
        typeof a.marker_detected === "boolean" &&
        typeof a.elapsed_ms === "number" &&
        (a.status === null || typeof a.status === "number"),
    ) &&
    (recheck === null ||
      (object(recheck) &&
        typeof recheck.marker_detected === "boolean" &&
        typeof recheck.outcome === "string" &&
        (recheck.fresh_token === undefined ||
          typeof recheck.fresh_token === "string"))) &&
    (explanation === undefined ||
      (object(explanation) &&
        strings(explanation.why) &&
        strings(explanation.remediation) &&
        typeof explanation.next_action === "string"))
  );
}
