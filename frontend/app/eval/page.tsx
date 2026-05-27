"use client";

import { useState } from "react";
import { apiFetch, type EvalRunResponse } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { TraceTimeline } from "@/components/TraceTimeline";

type CaseRow = EvalRunResponse["results"][number];

export default function EvalPage() {
  const [data, setData] = useState<EvalRunResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<EvalRunResponse>("/api/eval/run");
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Eval suite</h1>
          <p className="mt-2 text-ink-600">
            Run all 12 cases from <code>test_cases.json</code> through the
            pipeline and compare against expected outcomes.
          </p>
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="rounded-lg bg-ink-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-ink-800 disabled:opacity-50"
        >
          {loading ? "Running…" : data ? "Re-run" : "Run eval"}
        </button>
      </header>

      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      {data ? (
        <>
          <section className="rounded-2xl border border-ink-200 bg-white p-6">
            <div className="flex items-center gap-6">
              <Stat label="Total" value={data.total} />
              <Stat label="Passed" value={data.passed} tone="emerald" />
              <Stat label="Failed" value={data.failed} tone="rose" />
              <div className="ml-auto text-sm text-ink-600">
                {data.passed === data.total
                  ? "All cases passing"
                  : `${data.failed} case(s) failing`}
              </div>
            </div>
          </section>

          <MetricsSection results={data.results} />

          <section className="rounded-2xl border border-ink-200 bg-white p-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-ink-500">
                  <th className="py-2 pr-3 font-medium">Case</th>
                  <th className="py-2 pr-3 font-medium">Name</th>
                  <th className="py-2 pr-3 font-medium">Expected</th>
                  <th className="py-2 pr-3 font-medium">Got</th>
                  <th className="py-2 pr-3 font-medium">Approved</th>
                  <th className="py-2 pr-3 font-medium">Confidence</th>
                  <th className="py-2 font-medium">Result</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((r) => {
                  const expected =
                    (r.expected as { decision?: string }).decision ?? "EARLY_STOP";
                  const got = r.decision?.status ?? "EARLY_STOP";
                  const isOpen = expanded === r.case_id;
                  return (
                    <>
                      <tr
                        key={r.case_id}
                        className="cursor-pointer border-t border-ink-100 hover:bg-ink-50"
                        onClick={() =>
                          setExpanded((e) => (e === r.case_id ? null : r.case_id))
                        }
                      >
                        <td className="py-2 pr-3 font-mono text-xs">
                          {r.case_id}
                        </td>
                        <td className="py-2 pr-3">{r.case_name}</td>
                        <td className="py-2 pr-3">
                          <StatusBadge status={String(expected)} />
                        </td>
                        <td className="py-2 pr-3">
                          <StatusBadge status={got} />
                        </td>
                        <td className="py-2 pr-3 tabular-nums">
                          {r.decision
                            ? r.decision.approved_amount.toLocaleString("en-IN", {
                                style: "currency",
                                currency: "INR",
                                maximumFractionDigits: 0,
                              })
                            : "—"}
                        </td>
                        <td className="py-2 pr-3 tabular-nums">
                          {r.decision
                            ? `${Math.round(r.decision.confidence * 100)}%`
                            : "—"}
                        </td>
                        <td className="py-2">
                          <StatusBadge status={r.passed ? "PASS" : "FAIL"} />
                        </td>
                      </tr>
                      {isOpen ? (
                        <tr>
                          <td colSpan={7} className="bg-ink-50 p-4">
                            <div className="space-y-4">
                              {r.issues && r.issues.length > 0 ? (
                                <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                                  <div className="font-medium">Mismatches</div>
                                  <ul className="ml-4 list-disc">
                                    {r.issues.map((i, idx) => (
                                      <li key={idx}>{i}</li>
                                    ))}
                                  </ul>
                                </div>
                              ) : null}
                              {r.system_must_results.length > 0 ? (
                                <div className="rounded border border-ink-200 bg-white p-3">
                                  <div className="text-xs font-semibold uppercase text-ink-500">
                                    system_must checks
                                  </div>
                                  <ul className="mt-1 space-y-1">
                                    {r.system_must_results.map((m, idx) => (
                                      <li
                                        key={idx}
                                        className="flex items-start gap-2 text-sm"
                                      >
                                        <span
                                          className={
                                            m.satisfied
                                              ? "text-emerald-600"
                                              : "text-rose-600"
                                          }
                                        >
                                          {m.satisfied ? "✓" : "✗"}
                                        </span>
                                        <span>{m.requirement}</span>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              ) : null}
                              {r.early_stop_user_message ? (
                                <div className="rounded border border-sky-200 bg-sky-50 p-3 text-sm text-ink-800">
                                  <div className="text-xs font-semibold uppercase text-ink-500">
                                    Early-stop user message
                                  </div>
                                  <div className="mt-1">
                                    {r.early_stop_user_message}
                                  </div>
                                </div>
                              ) : null}
                              {r.decision ? (
                                <div className="rounded border border-ink-200 bg-white p-3">
                                  <div className="text-xs font-semibold uppercase text-ink-500">
                                    Decision user message
                                  </div>
                                  <div className="mt-1 text-sm">
                                    {r.decision.user_message}
                                  </div>
                                </div>
                              ) : null}
                              <div className="rounded border border-ink-200 bg-white p-3">
                                <div className="mb-2 text-xs font-semibold uppercase text-ink-500">
                                  Trace
                                </div>
                                <TraceTimeline trace={r.trace} />
                              </div>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </>
                  );
                })}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone?: "emerald" | "rose";
}) {
  const toneClass =
    tone === "emerald"
      ? "text-emerald-700"
      : tone === "rose"
        ? "text-rose-700"
        : "text-ink-900";
  return (
    <div>
      <div className="text-xs uppercase tracking-widest text-ink-500">
        {label}
      </div>
      <div className={`text-3xl font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}

function MetricsSection({ results }: { results: CaseRow[] }) {
  const latencies = results
    .map((r) => r.metrics?.total_latency_ms ?? 0)
    .sort((a, b) => a - b);
  if (latencies.length === 0) return null;
  const p50 = latencies[Math.floor(latencies.length / 2)];
  const p95 = latencies[Math.max(0, Math.floor(latencies.length * 0.95) - 1)];
  const tokens = results.reduce(
    (s, r) => s + (r.metrics?.tokens_in ?? 0) + (r.metrics?.tokens_out ?? 0),
    0
  );
  const usd = results.reduce((s, r) => s + (r.metrics?.usd_estimate ?? 0), 0);
  const issueCount = results.reduce(
    (s, r) => s + (r.metrics?.validation_issue_count ?? 0),
    0
  );
  const contradictionCount = results.reduce(
    (s, r) => s + (r.metrics?.contradictions.length ?? 0),
    0
  );
  const deliberationCount = results.reduce(
    (s, r) =>
      s +
      Object.values(r.metrics?.deliberation_iterations ?? {}).reduce(
        (a, b) => a + b,
        0
      ),
    0
  );

  const buckets = new Array(10).fill(0) as number[];
  for (const r of results) {
    for (const c of r.metrics?.extraction_confidences ?? []) {
      const idx = Math.min(9, Math.max(0, Math.floor(c * 10)));
      buckets[idx]++;
    }
  }
  const maxBucket = Math.max(...buckets, 1);

  const ruleToCases = new Map<string, string[]>();
  for (const r of results) {
    for (const rid of r.metrics?.fired_rules ?? []) {
      if (!ruleToCases.has(rid)) ruleToCases.set(rid, []);
      ruleToCases.get(rid)!.push(r.case_id);
    }
  }

  return (
    <section className="rounded-2xl border border-ink-200 bg-white p-6">
      <h2 className="text-lg font-semibold">Aggregate metrics</h2>
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Latency P50" value={`${p50} ms`} />
        <Stat label="Latency P95" value={`${p95} ms`} />
        <Stat label="Total tokens" value={tokens.toLocaleString()} />
        <Stat label="Est. cost" value={`$${usd.toFixed(6)}`} />
        <Stat label="Validation issues" value={issueCount} />
        <Stat label="Contradictions" value={contradictionCount} />
        <Stat label="Deliberation cycles" value={deliberationCount} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
            Extraction confidence histogram
          </div>
          <div className="space-y-1">
            {buckets.map((n, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="w-16 font-mono text-ink-500">
                  [{(i / 10).toFixed(1)}–{((i + 1) / 10).toFixed(1)})
                </span>
                <div className="flex-1 overflow-hidden rounded bg-ink-50">
                  <div
                    className="h-3 bg-ink-700"
                    style={{ width: `${(n / maxBucket) * 100}%` }}
                  />
                </div>
                <span className="w-6 text-right font-mono">{n}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
            Rule coverage
          </div>
          {ruleToCases.size === 0 ? (
            <div className="text-sm text-ink-500">
              No policy rules fired in this run.
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead className="text-left uppercase text-ink-500">
                <tr>
                  <th className="py-1 pr-3">Rule</th>
                  <th className="py-1 pr-3">Fired in</th>
                  <th className="py-1 text-right">Count</th>
                </tr>
              </thead>
              <tbody>
                {[...ruleToCases.entries()].sort().map(([rid, cases]) => (
                  <tr key={rid} className="border-t border-ink-100">
                    <td className="py-1 pr-3 font-mono">{rid}</td>
                    <td className="py-1 pr-3 text-ink-700">
                      {cases.join(", ")}
                    </td>
                    <td className="py-1 text-right tabular-nums">
                      {cases.length}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </section>
  );
}
