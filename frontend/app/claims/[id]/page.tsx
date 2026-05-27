"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch, type ClaimStateResponse } from "@/lib/api";
import { DecisionCard } from "@/components/DecisionCard";
import { DecisionTree } from "@/components/DecisionTree";
import { TraceTimeline } from "@/components/TraceTimeline";
import { ExtractedDocs } from "@/components/ExtractedDocs";
import { StatusBadge } from "@/components/StatusBadge";

export default function ClaimDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [data, setData] = useState<ClaimStateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    apiFetch<ClaimStateResponse>(`/api/claims/${id}`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [id]);

  if (error) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
        Could not load claim {id}: {error}
        <div className="mt-2">
          <Link href="/submit" className="underline">
            Submit a new claim
          </Link>
        </div>
      </div>
    );
  }

  if (!data) return <div className="text-ink-500">Loading…</div>;

  const { state } = data;

  return (
    <div className="space-y-8">
      <header className="flex items-start justify-between">
        <div>
          <div className="text-xs uppercase tracking-widest text-ink-500">
            Claim
          </div>
          <h1 className="mt-1 font-mono text-2xl font-semibold tracking-tight">
            {state.claim_id}
          </h1>
          <div className="mt-1 text-sm text-ink-600">
            Member{" "}
            <span className="font-mono">
              {(state.input as { member_id: string }).member_id}
            </span>{" "}
            · {(state.input as { claim_category: string }).claim_category}
          </div>
        </div>
        <Link
          href="/submit"
          className="rounded-lg border border-ink-200 bg-white px-4 py-2 text-sm font-medium hover:bg-ink-50"
        >
          + New claim
        </Link>
      </header>

      {state.early_stop && !state.decision ? (
        <section className="rounded-2xl border border-sky-200 bg-sky-50 p-6">
          <div className="flex items-center gap-3">
            <StatusBadge status="EARLY_STOP" />
            <span className="font-mono text-sm">
              {state.early_stop_reason}
            </span>
          </div>
          <p className="mt-3 text-sm text-ink-800">
            {state.early_stop_user_message}
          </p>
        </section>
      ) : null}

      {state.decision ? <DecisionCard decision={state.decision} /> : null}

      {state.decision?.explanation_tree ? (
        <DecisionTree root={state.decision.explanation_tree} />
      ) : null}

      <section className="rounded-2xl border border-ink-200 bg-white p-6">
        <h3 className="text-lg font-semibold">Trace timeline</h3>
        <p className="mt-1 text-sm text-ink-600">
          Every node the pipeline ran, in order, with timing, confidence
          delta, and full evidence on click.
        </p>
        <div className="mt-5">
          <TraceTimeline trace={state.trace} />
        </div>
      </section>

      <ExtractedDocs docs={state.extracted} />
    </div>
  );
}
