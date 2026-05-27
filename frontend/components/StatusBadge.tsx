import { twMerge } from "tailwind-merge";

const STATUS_STYLES: Record<string, string> = {
  APPROVED: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  PARTIAL: "bg-amber-100 text-amber-800 ring-amber-200",
  REJECTED: "bg-rose-100 text-rose-800 ring-rose-200",
  MANUAL_REVIEW: "bg-violet-100 text-violet-800 ring-violet-200",
  NEEDS_REUPLOAD: "bg-sky-100 text-sky-800 ring-sky-200",
  NEEDS_CORRECTION: "bg-sky-100 text-sky-800 ring-sky-200",
  NEEDS_CLARIFICATION: "bg-indigo-100 text-indigo-800 ring-indigo-200",
  ESCALATED_MEDICAL_REVIEW: "bg-fuchsia-100 text-fuchsia-800 ring-fuchsia-200",
  FRAUD_INVESTIGATION: "bg-red-100 text-red-800 ring-red-200",
  OK: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  WARNING: "bg-amber-100 text-amber-800 ring-amber-200",
  ERROR: "bg-rose-100 text-rose-800 ring-rose-200",
  EARLY_STOP: "bg-sky-100 text-sky-800 ring-sky-200",
  SKIPPED: "bg-ink-100 text-ink-700 ring-ink-200",
  PASS: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  FAIL: "bg-rose-100 text-rose-800 ring-rose-200",
};

export function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const style = STATUS_STYLES[status] ?? "bg-ink-100 text-ink-700 ring-ink-200";
  return (
    <span
      className={twMerge(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        style,
        className
      )}
    >
      {status}
    </span>
  );
}
