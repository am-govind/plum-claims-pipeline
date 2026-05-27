"use client";

import { useState } from "react";
import type { TraceStep } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";

export function TraceTimeline({ trace }: { trace: TraceStep[] }) {
  return (
    <ol className="relative space-y-3 border-l border-ink-200 pl-6">
      {trace.map((step, i) => (
        <TraceItem key={`${step.step}-${i}`} step={step} />
      ))}
    </ol>
  );
}

function TraceItem({ step }: { step: TraceStep }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="relative">
      <span className="absolute -left-[29px] flex h-4 w-4 items-center justify-center rounded-full bg-white ring-2 ring-ink-300" />
      <div className="rounded-lg border border-ink-200 bg-white">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-start gap-3 p-3 text-left hover:bg-ink-50"
        >
          <StatusBadge status={step.status} />
          <div className="flex-1">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="font-mono text-sm font-medium">
                {step.step}
              </span>
              <span className="text-xs text-ink-500">
                {step.latency_ms}ms
                {step.confidence_delta !== 0 ? (
                  <span className="ml-2">
                    Δ confidence{" "}
                    <span
                      className={
                        step.confidence_delta < 0
                          ? "text-rose-600"
                          : "text-emerald-600"
                      }
                    >
                      {step.confidence_delta > 0 ? "+" : ""}
                      {step.confidence_delta.toFixed(2)}
                    </span>
                  </span>
                ) : null}
              </span>
            </div>
            <div className="mt-0.5 text-sm text-ink-700">{step.summary}</div>
            {step.error ? (
              <div className="mt-1 font-mono text-xs text-rose-600">
                {step.error}
              </div>
            ) : null}
          </div>
          <span className="text-xs text-ink-400">{open ? "▾" : "▸"}</span>
        </button>
        {open && Object.keys(step.evidence ?? {}).length > 0 ? (
          <pre className="overflow-x-auto border-t border-ink-200 bg-ink-50 p-3 text-xs text-ink-700">
            {JSON.stringify(step.evidence, null, 2)}
          </pre>
        ) : null}
      </div>
    </li>
  );
}
