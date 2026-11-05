"use client";
import { useCallback, useEffect, useState } from "react";
export function useRemote<T>(
  url: string,
  interval = 15_000,
  terminal?: (data: T) => boolean,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [updated, setUpdated] = useState<Date | null>(null);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController | undefined;
    let failures = 0;
    async function load() {
      if (stopped) return;
      if (document.hidden) {
        timer = setTimeout(load, interval);
        return;
      }
      controller = new AbortController();
      let delay = interval;
      let finished = false;
      setLoading(true);
      try {
        const response = await fetch(url, {
          cache: "no-store",
          signal: AbortSignal.any([
            controller.signal,
            AbortSignal.timeout(15_000),
          ]),
        });
        const result = await response.json();
        if (!response.ok) {
          finished = [401, 403, 404].includes(response.status);
          if (response.status === 429)
            delay = Math.max(
              interval,
              Math.min(
                300_000,
                Number(response.headers.get("Retry-After") || 30) * 1000,
              ),
            );
          throw new Error(
            response.status === 401
              ? "Your session has expired. Sign in again to continue."
              : result.error || "This view could not refresh.",
          );
        }
        if (!stopped) {
          setData(result);
          setError("");
          setUpdated(new Date());
          failures = 0;
          finished = terminal?.(result) ?? false;
        }
      } catch (e) {
        if (!stopped) {
          setError(e instanceof Error ? e.message : "Connection interrupted.");
          failures++;
          delay = Math.max(delay, Math.min(120_000, interval * 2 ** failures));
        }
      } finally {
        if (!stopped) {
          setLoading(false);
          if (!finished) timer = setTimeout(load, delay);
        }
      }
    }
    void load();
    return () => {
      stopped = true;
      clearTimeout(timer);
      controller?.abort();
    };
  }, [url, interval, revision, terminal]);
  return { data, error, loading, updated, reload };
}
