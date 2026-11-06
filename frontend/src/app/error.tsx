"use client";
import Link from "next/link";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="standalone-state">
      <h1>This view couldn’t load.</h1>
      <p>
        Try loading it again. No investigation has been submitted by this
        action.
      </p>
      <button className="button primary-button" onClick={reset}>
        Try again
      </button>
      <Link href="/">Return home</Link>
    </main>
  );
}
