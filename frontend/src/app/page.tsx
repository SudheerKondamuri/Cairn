import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Code2,
  FileCheck2,
  Fingerprint,
  GitBranch,
  MoveUpRight,
} from "lucide-react";
import { Navigation } from "@/components/navigation";
import { HeroArt } from "@/components/hero-art";
import { CairnMark, Wordmark } from "@/components/brand";
import { Evidence, type CaseEvidence } from "@/components/evidence";
import vulnerable from "../../public/evidence/northstar-vulnerable.json";
import patched from "../../public/evidence/northstar-patched.json";

const repository = "https://github.com/SudheerKondamuri/Cairn";
const cases: CaseEvidence[] = [
  {
    key: "vulnerable",
    version: "1.4.2",
    verdict: "Command injection verified",
    hash: vulnerable.evidence.source_hash,
    attempts: vulnerable.evidence.attempts.length,
    marker: vulnerable.evidence.attempts.some(
      (attempt) => attempt.marker_detected,
    ),
    independent: vulnerable.evidence.independent_recheck.marker_detected,
    payload: vulnerable.evidence.request.param_value,
    route: vulnerable.evidence.request.path,
    source: [
      "result = subprocess.run(",
      "    f\"printf 'resolved target=%s\\\\n' {host}\",",
      "    shell=True,",
      "    capture_output=True,",
      "    text=True,",
      "    timeout=5,",
      "    check=False,",
      ")",
    ],
    download: "/evidence/northstar-vulnerable.json",
  },
  {
    key: "patched",
    version: "1.4.3",
    verdict: "Claim not reproduced",
    hash: patched.evidence.source_hash,
    attempts: patched.evidence.attempts.length,
    marker: patched.evidence.attempts.some(
      (attempt) => attempt.marker_detected,
    ),
    independent: null,
    payload: patched.evidence.attempts[1].param_value,
    route: patched.evidence.request.path,
    source: [
      "result = subprocess.run(",
      '    ["printf", "resolved target=%s\\n", host],',
      "    shell=False,",
      "    capture_output=True,",
      "    text=True,",
      "    timeout=5,",
      "    check=False,",
      ")",
    ],
    download: "/evidence/northstar-patched.json",
  },
];

export default function Home() {
  return (
    <>
      <main id="main">
        <a className="skip-link" href="#hero-heading">
          Skip to content
        </a>
        <div className="hero-ground" id="top">
          <Navigation />
          <section className="hero" aria-labelledby="hero-heading">
            <div className="hero-copy">
              <h1 id="hero-heading">
                <span>Security claims.</span>
                <span>Meet reality.</span>
              </h1>
              <p className="hero-description">
                Automated reproduction engine for command-injection security
                reports. Real execution in isolated Celesto microVMs.
                Independently verified proof markers.
              </p>
              <div className="hero-actions">
                <a className="button primary-button" href="#investigation">
                  See it investigate <ArrowUpRight size={19} />
                </a>
                <a className="quiet-link" href="#how-it-works">
                  How Cairn works <ArrowRight size={17} />
                </a>
              </div>
              <div className="powered-by">
                <span className="celesto-mark" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                </span>
                <span>
                  Execution powered by <strong>Celesto</strong>
                </span>
              </div>
            </div>
            <HeroArt />
            <div className="hero-footnote">
              <span>Built for the moment “probably” isn’t enough.</span>
              <a
                href="#investigation"
                aria-label="Scroll to the recorded investigation"
              >
                <ArrowDown size={18} />
              </a>
            </div>
          </section>
        </div>

        <section className="intro-band" aria-label="Cairn's approach">
          <div className="intro-band-inner">
            <CairnMark />
            <p>
              A report makes a claim.
              <br />
              <strong>Cairn makes it testable.</strong>
            </p>
            <span>
              From a line of source code
              <br />
              to a trace you can follow.
            </span>
          </div>
        </section>

        <section
          className="investigation section-wrap"
          id="investigation"
          aria-labelledby="investigation-heading"
        >
          <div className="section-intro">
            <h2 id="investigation-heading">
              Same claim.
              <br />
              Different evidence.
            </h2>
            <div>
              <p>
                A shell injection report. A vulnerable application. A patched
                version. Follow what actually happened when Cairn investigated
                each one.
              </p>
              <span className="interaction-hint">
                <GitBranch size={15} /> Switch the source. Inspect the outcome.
              </span>
            </div>
          </div>
          <Evidence cases={cases} />
        </section>

        <section
          className="method-section"
          id="how-it-works"
          aria-labelledby="method-heading"
        >
          <div className="section-wrap method-inner">
            <div className="method-opening">
              <h2 id="method-heading">
                Curiosity,
                <br />
                with boundaries.
              </h2>
              <p>
                The agent gets a real computer.
                <br />
                The conclusion still has to earn your trust.
              </p>
            </div>
            <div className="method-layout">
              <div
                className="boundary-visual"
                role="img"
                aria-label="The trusted controller sends an investigation to a Celesto sandbox containing the application and bounded tools. Evidence returns to the controller for an independent recheck."
              >
                <div className="control-node">
                  <CairnMark />
                  <span>Cairn controller</span>
                  <span className="control-note">The trusted side</span>
                </div>
                <div className="boundary-connection">
                  <span>Investigation</span>
                  <div className="connection-lines">
                    <span />
                    <span />
                  </div>
                  <span>Evidence</span>
                </div>
                <div className="guest-boundary">
                  <div className="guest-header">
                    <span className="celesto-mark" aria-hidden="true">
                      <i />
                      <i />
                      <i />
                    </span>
                    <strong>Celesto sandbox</strong>
                    <span className="guest-caption">The execution side</span>
                  </div>
                  <div className="guest-content">
                    <div>
                      <Code2 size={25} />
                      <span>Your application</span>
                    </div>
                    <div className="guest-cross">+</div>
                    <div>
                      <Fingerprint size={25} />
                      <span>Bounded tools</span>
                    </div>
                  </div>
                  <p>Subject code executes inside the guest.</p>
                </div>
                <div className="boundary-note">
                  <FileCheck2 size={17} />
                  <span>A fresh marker request checks the finding again.</span>
                </div>
              </div>
              <ol className="method-steps">
                <li>
                  <span className="step-number">01</span>
                  <div>
                    <h3>Start with the claim.</h3>
                    <p>
                      Cairn reads the report and source to identify the route,
                      input, and behavior worth testing.
                    </p>
                  </div>
                </li>
                <li>
                  <span className="step-number">02</span>
                  <div>
                    <h3>Let the code answer.</h3>
                    <p>
                      The application runs in a Celesto guest. Bounded tools
                      make requests and look for harmless marker evidence.
                    </p>
                  </div>
                </li>
                <li>
                  <span className="step-number">03</span>
                  <div>
                    <h3>Check the evidence again.</h3>
                    <p>
                      A positive finding needs a separate request from the
                      controller with a fresh marker. Then the report preserves
                      the result.
                    </p>
                  </div>
                </li>
              </ol>
            </div>
            <div className="method-bottom">
              <span>Inspectable by design.</span>
              <a
                href={`${repository}/tree/main/core`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Read the investigation code <ArrowUpRight size={17} />
              </a>
            </div>
          </div>
        </section>

        <section
          className="open-section section-wrap"
          aria-labelledby="open-heading"
        >
          <div className="open-copy">
            <h2 id="open-heading">
              The work is open.
              <br />
              So is the evidence.
            </h2>
            <p>
              Read the implementation. Download a report. Challenge the
              conclusion. You shouldn’t have to take an investigator at its
              word.
            </p>
          </div>
          <div className="resource-list">
            <a
              href={`${repository}#readme`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <span>
                <BookOpen size={21} />
                <span>
                  <strong>Understand the project</strong>
                  <small>Architecture, setup, and tradeoffs</small>
                </span>
              </span>
              <ArrowUpRight size={22} />
            </a>
            <a
              href="/guide"
              target="_blank"
              rel="noopener noreferrer"
            >
              <span>
                <FileCheck2 size={21} />
                <span>
                  <strong>Run your first investigation</strong>
                  <small>Source, runtime settings, and reading your result</small>
                </span>
              </span>
              <ArrowUpRight size={22} />
            </a>
            <a href={repository} target="_blank" rel="noopener noreferrer">
              <span>
                <Code2 size={21} />
                <span>
                  <strong>Explore the source</strong>
                  <small>Follow an investigation through the code</small>
                </span>
              </span>
              <ArrowUpRight size={22} />
            </a>
          </div>
        </section>
      </main>
      <footer className="site-footer">
        <div className="footer-top section-wrap">
          <div>
            <span className="footer-invitation">Go beyond the claim.</span>
            <a href="/operator">
              Start investigating <MoveUpRight size={35} />
            </a>
          </div>
          <p>
            Automated reproduction inside isolated Celesto MicroVMs.
            <br />Independently verified proof markers.
          </p>
        </div>
        <div className="footer-wordmark" aria-hidden="true">
          cairn
          <span>
            <CairnMark />
          </span>
        </div>
        <div className="footer-bottom section-wrap">
          <a href="#top" aria-label="Cairn home">
            <Wordmark />
          </a>
          <span>Built by Sudheer Kondamuri</span>
          <a href={repository} target="_blank" rel="noopener noreferrer">
            View on GitHub <ArrowUpRight size={14} />
          </a>
        </div>
      </footer>
    </>
  );
}
