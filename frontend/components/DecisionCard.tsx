import type { ConfidenceBreakdown, Decision } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";

export function DecisionCard({ decision }: { decision: Decision }) {
  const confidencePct = Math.round((decision.confidence ?? 0) * 100);
  const cb = decision.confidence_breakdown as ConfidenceBreakdown | undefined;
  const hasBreakdown = !!cb && typeof cb.final === "number";
  return (
    <section className="rounded-2xl border border-ink-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-ink-500">
            Decision
          </div>
          <div className="mt-1 flex items-center gap-3">
            <StatusBadge status={decision.status} />
            {decision.degraded ? <StatusBadge status="WARNING" /> : null}
            {decision.requires_manual_review ? (
              <StatusBadge status="MANUAL_REVIEW" />
            ) : null}
          </div>
          <div className="mt-2 text-2xl font-semibold tracking-tight">
            {currency(decision.approved_amount)}
            <span className="ml-2 text-sm font-normal text-ink-500">
              of {currency(decision.submitted_amount)} claimed
            </span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-widest text-ink-500">
            Confidence
          </div>
          <div className="mt-1 text-2xl font-semibold tracking-tight">
            {confidencePct}%
          </div>
          <div className="mt-2 h-2 w-32 overflow-hidden rounded-full bg-ink-100">
            <div
              className="h-full bg-ink-900"
              style={{ width: `${confidencePct}%` }}
            />
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-lg bg-ink-50 p-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-ink-500">
          Summary
        </div>
        <div className="mt-1 text-sm text-ink-800">{decision.summary}</div>
        <div className="mt-3 text-xs font-semibold uppercase tracking-wide text-ink-500">
          Member message
        </div>
        <div className="mt-1 text-sm text-ink-700">{decision.user_message}</div>
        {decision.notes && decision.notes.length > 0 ? (
          <div className="mt-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-ink-500">
              Notes
            </div>
            <ul className="mt-1 list-disc pl-5 text-sm text-ink-700">
              {decision.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {decision.rejection_reasons && decision.rejection_reasons.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {decision.rejection_reasons.map((r) => (
              <StatusBadge key={r} status="FAIL" className="!bg-rose-50" />
            ))}
            {decision.rejection_reasons.map((r) => (
              <span
                key={`${r}-text`}
                className="font-mono text-xs text-rose-700"
              >
                {r}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      {decision.line_items && decision.line_items.length > 0 ? (
        <div className="mt-6">
          <div className="text-xs font-semibold uppercase tracking-wide text-ink-500">
            Line items
          </div>
          <table className="mt-2 w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-ink-500">
                <th className="py-2 pr-3 font-medium">Description</th>
                <th className="py-2 pr-3 font-medium">Submitted</th>
                <th className="py-2 pr-3 font-medium">Approved</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {decision.line_items.map((li, i) => (
                <tr key={i} className="border-t border-ink-100">
                  <td className="py-2 pr-3">{li.description}</td>
                  <td className="py-2 pr-3 tabular-nums">
                    {currency(li.submitted_amount)}
                  </td>
                  <td className="py-2 pr-3 tabular-nums">
                    {currency(li.approved_amount)}
                  </td>
                  <td className="py-2 pr-3">
                    <StatusBadge status={li.status} />
                  </td>
                  <td className="py-2 text-xs text-ink-600">
                    {li.reason ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {hasBreakdown ? (
        <details className="mt-6 rounded-lg border border-ink-200">
          <summary className="cursor-pointer p-3 text-sm font-medium text-ink-700">
            How was this confidence calculated?
          </summary>
          <div className="border-t border-ink-200 bg-ink-50 p-3 text-xs">
            <div className="text-ink-600">
              C_final = clip(Σ wᵢ·Cᵢ − α·contradictions − β·degraded, 0, 1)
            </div>
            <table className="mt-2 w-full">
              <thead className="text-left text-[10px] uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="py-1 pr-3 font-medium">Agent</th>
                  <th className="py-1 pr-3 font-medium">Weight</th>
                  <th className="py-1 pr-3 font-medium">Confidence</th>
                  <th className="py-1 font-medium">Contribution</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {Object.entries(cb!.per_component).map(([k, v]) => (
                  <tr key={k} className="border-t border-ink-100">
                    <td className="py-1 pr-3 text-ink-700">{k}</td>
                    <td className="py-1 pr-3 tabular-nums">{v.weight.toFixed(2)}</td>
                    <td className="py-1 pr-3 tabular-nums">
                      {v.confidence.toFixed(2)}
                    </td>
                    <td className="py-1 tabular-nums">
                      {v.contribution.toFixed(3)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-ink-200 font-mono">
                  <td className="py-1 pr-3 text-ink-600">Σ wᵢ·Cᵢ</td>
                  <td colSpan={2} />
                  <td className="py-1 tabular-nums">
                    {cb!.weighted_sum.toFixed(3)}
                  </td>
                </tr>
                <tr className="font-mono text-rose-700">
                  <td className="py-1 pr-3">
                    − α·contradictions (α={cb!.alpha})
                  </td>
                  <td colSpan={2} />
                  <td className="py-1 tabular-nums">
                    −{cb!.contradiction_penalty.toFixed(3)}
                  </td>
                </tr>
                <tr className="font-mono text-rose-700">
                  <td className="py-1 pr-3">
                    − β·degraded (β={cb!.beta})
                  </td>
                  <td colSpan={2} />
                  <td className="py-1 tabular-nums">
                    −{cb!.degraded_penalty.toFixed(3)}
                  </td>
                </tr>
                <tr className="border-t border-ink-200 font-semibold font-mono">
                  <td className="py-1 pr-3">C_final</td>
                  <td colSpan={2} />
                  <td className="py-1 tabular-nums">
                    {cb!.final.toFixed(3)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </details>
      ) : null}

      {decision.breakdown && Object.keys(decision.breakdown).length > 0 ? (
        <details className="mt-3 rounded-lg border border-ink-200">
          <summary className="cursor-pointer p-3 text-sm font-medium text-ink-700">
            Calculation breakdown
          </summary>
          <pre className="overflow-x-auto rounded-b-lg bg-ink-50 p-3 text-xs">
            {JSON.stringify(decision.breakdown, null, 2)}
          </pre>
        </details>
      ) : null}

      {decision.cost ? <CostFooter cost={decision.cost} /> : null}
    </section>
  );
}

function CostFooter({ cost }: { cost: NonNullable<Decision["cost"]> }) {
  const tokensIn = cost.llm_calls.reduce((s, c) => s + c.tokens_in, 0);
  const tokensOut = cost.llm_calls.reduce((s, c) => s + c.tokens_out, 0);
  const usd = cost.llm_calls.reduce((s, c) => s + c.usd_estimate, 0);
  const totalLatency = cost.node_latencies.reduce((s, n) => s + n.latency_ms, 0);
  if (cost.llm_calls.length === 0 && cost.node_latencies.length === 0) return null;
  return (
    <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-ink-100 pt-3 text-xs text-ink-500">
      <div>
        <span className="font-mono">{cost.llm_calls.length}</span> LLM call(s) ·{" "}
        <span className="font-mono">{(tokensIn + tokensOut).toLocaleString()}</span> tokens
        ({tokensIn} in / {tokensOut} out)
      </div>
      <div>
        ≈ ${usd.toFixed(6)} · pipeline {totalLatency} ms
      </div>
    </div>
  );
}

function currency(n: number): string {
  return n.toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  });
}
