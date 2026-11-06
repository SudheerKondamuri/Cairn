import Link from "next/link";
import { ArrowRight, GitBranch } from "lucide-react";
import { Wordmark } from "./brand";
export function SignIn({
  providers,
  error,
}: {
  providers: { google: boolean; github: boolean };
  error?: boolean;
}) {
  return (
    <main className="signin-page">
      <div className="signin-story">
        <Link href="/">
          <Wordmark />
        </Link>
        <div>
          <h1>
            A claim.
            <br />A computer.
            <br />
            Your evidence.
          </h1>
          <p>
            Three investigations to put Cairn to work.
            <br />
            Your source and results stay private.
          </p>
        </div>
        <Link href="/investigations">
          Explore a recorded investigation <ArrowRight size={17} />
        </Link>
      </div>
      <div className="signin-form-wrap">
        <div className="signin-form">
          <h2>Your investigation starts here.</h2>
          <p>
            Sign in or create your account. Choose the same provider each time
            to return to your history.
          </p>
          {error && (
            <p className="form-error" role="alert">
              Sign-in could not be completed. Try again, or explore the public
              examples while the service is unavailable.
            </p>
          )}
          <div className="oauth-buttons">
            <a
              className={`button primary-button ${!providers.github ? "is-disabled" : ""}`}
              href={providers.github ? "/api/auth/github" : undefined}
              aria-disabled={!providers.github}
            >
              <GitBranch size={19} />
              Continue with GitHub
            </a>
            <a
              className={`button secondary-button ${!providers.google ? "is-disabled" : ""}`}
              href={providers.google ? "/api/auth/google" : undefined}
              aria-disabled={!providers.google}
            >
              Continue with Google <ArrowRight size={17} />
            </a>
          </div>
          {!providers.google && !providers.github && (
            <p className="notice">
              Account sign-in is not available on this deployment yet. Published
              evidence remains open.
            </p>
          )}
          <p className="signin-note">
            Three live runs per account. No card required. Availability depends
            on the shared trial capacity.
          </p>
          <Link href="/privacy">How Cairn handles your source and data</Link>
        </div>
      </div>
    </main>
  );
}
