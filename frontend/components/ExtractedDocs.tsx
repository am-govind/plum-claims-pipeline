import type { ClaimStateResponse } from "@/lib/api";

type Extracted = ClaimStateResponse["state"]["extracted"][number];

export function ExtractedDocs({ docs }: { docs: Extracted[] }) {
  if (!docs || docs.length === 0) {
    return null;
  }
  return (
    <section className="rounded-2xl border border-ink-200 bg-white p-6">
      <h3 className="text-lg font-semibold">Extracted document fields</h3>
      <p className="mt-1 text-sm text-ink-600">
        Structured data the extraction agent pulled out of each document.
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {docs.map((d, i) => (
          <div key={i} className="rounded-lg border border-ink-200 p-4">
            <div className="flex items-center justify-between">
              <div className="font-mono text-sm">
                {(d.file_id as string) ?? `doc_${i}`}
              </div>
              <span className="text-xs uppercase tracking-wide text-ink-500">
                {(d.document_type as string) ?? "UNKNOWN"}
              </span>
            </div>
            <dl className="mt-3 space-y-1 text-sm">
              {entries(d).map(([k, v]) => (
                <div key={k} className="flex gap-3">
                  <dt className="w-44 shrink-0 text-xs text-ink-500">{k}</dt>
                  <dd className="flex-1 break-words text-ink-800">
                    {renderValue(v)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </section>
  );
}

function entries(d: Record<string, unknown>) {
  const fields = [
    "patient_name",
    "doctor_name",
    "doctor_registration",
    "diagnosis",
    "treatment",
    "medicines",
    "tests_ordered",
    "hospital_name",
    "document_date",
    "total_amount",
    "extraction_confidence",
  ];
  return fields
    .filter((f) => d[f] !== undefined && d[f] !== null && d[f] !== "")
    .map((f) => [f, d[f]] as const);
}

function renderValue(v: unknown): string {
  if (Array.isArray(v)) return v.length === 0 ? "—" : v.join(", ");
  if (typeof v === "number") return v.toLocaleString();
  if (v === null || v === undefined) return "—";
  return String(v);
}
