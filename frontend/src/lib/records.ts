const object = (x: unknown): x is Record<string, unknown> =>
  !!x && typeof x === "object" && !Array.isArray(x);
export function validRecord(x: unknown): boolean {
  return (
    object(x) &&
    typeof x.investigation_id === "string" &&
    /^inv-[a-zA-Z0-9-]{1,100}$/.test(x.investigation_id) &&
    ["queued", "running", "completed", "failed", "cancelled"].includes(String(x.status)) &&
    typeof x.created_at === "string" &&
    typeof x.updated_at === "string"
  );
}
export function validHistory(x: unknown): boolean {
  return (
    object(x) &&
    Array.isArray(x.items) &&
    x.items.length <= 25 &&
    x.items.every(
      (row) =>
        validRecord(row) &&
        typeof row.title === "string" &&
        (row.verdict === null || typeof row.verdict === "string"),
    ) &&
    (x.next_cursor === null ||
      (typeof x.next_cursor === "string" &&
        /^inv-[a-zA-Z0-9-]{1,100}$/.test(x.next_cursor)))
  );
}
