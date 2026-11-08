import Link from "next/link";
import { WorkspaceShell } from "@/components/workspace-shell";
import { signedIn, localAccessEnabled } from "@/lib/auth";
export const metadata = { title: "Data & trial access · Cairn" };
export default async function Page() {
  const isAuth = await signedIn();
  const isLocal = await localAccessEnabled();
  return (
    <WorkspaceShell operator={isAuth} local={isLocal}>
      <article className="content-panel policy-page">
        <h1>Your source. Your evidence.</h1>
        <p>
          Cairn is a public research trial for investigating command-injection
          claims against source you own or have permission to test.
        </p>
        <h2>Accounts and access</h2>
        <p>
          Google or GitHub confirms your identity. Cairn stores the provider’s
          account identifier and a private Cairn account ID. It does not store
          your provider password or retain the provider access token. Use the
          same provider to return to the same account.
        </p>
        <h2>Three investigations</h2>
        <p>
          Each account starts with three lifetime investigations. The deployment
          has a shared allowance of 50. Invalid submissions use no allowance.
          Jobs reserve an allowance when accepted; a confirmed failure or
          cancellation before execution releases it. Completed, inconclusive,
          and cancelled-after-start runs count. Provider availability can
          interrupt the trial.
        </p>
        <h2>Source and model processing</h2>
        <p>
          Source archives and fetched public repositories are staged privately,
          validated, and supplied to an isolated Celesto guest. The configured
          model provider receives the claim and tool observations, which can
          include source snippets. Only submit material you are permitted to
          process this way. Remove credentials before uploading.
        </p>
        <h2>Retention and sharing</h2>
        <p>
          Source archives are removed after execution. Reports are available for
          30 days, and you can delete a finished report sooner. Reports may
          contain payloads, response bodies, and source snippets. Sharing is
          optional: review the exact report before creating a link. Anyone
          holding that link can read it until you revoke it or the report
          expires. Quota and account records are retained to enforce trial
          limits.
        </p>
        <h2>Administration</h2>
        <p>
          The administrator can view account identifiers, allowance usage, and
          job states. The admin interface does not expose private report
          contents. Infrastructure administrators necessarily control the
          underlying storage.
        </p>
        <p>
          <Link href="/operator">Open your workspace</Link> ·{" "}
          <a href="https://github.com/SudheerKondamuri/Cairn">
            Source and local setup
          </a>
        </p>
      </article>
    </WorkspaceShell>
  );
}
