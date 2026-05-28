import Link from "next/link";
import { IS_DEV_MODE } from "@/lib/devMode";

export default function HomePage() {
  return (
    <div className="space-y-12">
      <section className="rounded-2xl bg-white border border-ink-200 p-10 shadow-sm">
        <div className="text-xs uppercase tracking-widest text-ink-500">
          Plum AI Engineer Assignment
        </div>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">
          A multi-agent claims pipeline you can audit end-to-end.
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-ink-600">
          Submit a health insurance claim. Our agents verify documents,
          extract structured data, apply policy rules, calculate the
          approved amount, screen for fraud, and produce a fully traced
          decision in seconds.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/submit"
            className="inline-flex items-center justify-center rounded-lg bg-ink-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-ink-800"
          >
            Submit a claim
          </Link>
          {IS_DEV_MODE ? (
            <Link
              href="/eval"
              className="inline-flex items-center justify-center rounded-lg border border-ink-200 bg-white px-5 py-2.5 text-sm font-medium text-ink-700 hover:bg-ink-50"
            >
              Run the eval suite
            </Link>
          ) : null}
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        {[
          {
            title: "Document verification first",
            body: "Wrong docs, unreadable photos, and patient mismatches are caught before any LLM call. Members get a specific, actionable message — not a generic error.",
          },
          {
            title: "Decisions you can audit",
            body: "Every step writes a structured trace step. Reviewers can reconstruct exactly what was checked, what passed, and how the final number was calculated.",
          },
          {
            title: "Resilient by design",
            body: "Non-critical agent failures degrade gracefully: confidence drops, manual review is recommended, the pipeline continues. No 500 errors.",
          },
        ].map((c) => (
          <div
            key={c.title}
            className="rounded-xl border border-ink-200 bg-white p-6"
          >
            <h3 className="text-lg font-semibold">{c.title}</h3>
            <p className="mt-2 text-sm text-ink-600">{c.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
