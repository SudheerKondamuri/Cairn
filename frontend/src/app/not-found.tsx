import Link from "next/link";
import { Wordmark } from "@/components/brand";
export default function NotFound() {
  return (
    <main className="standalone-state">
      <Link href="/">
        <Wordmark />
      </Link>
      <span className="large-state-number">404</span>
      <h1>This path ends here.</h1>
      <p>The page or published investigation could not be found.</p>
      <Link className="button primary-button" href="/investigations">
        Browse investigations
      </Link>
    </main>
  );
}
