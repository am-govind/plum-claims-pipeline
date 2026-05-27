import type { DecisionNode } from "@/lib/api";

const KIND_ICONS: Record<DecisionNode["kind"], string> = {
  root: "▣",
  rule_group: "▸",
  rule: "•",
  calc_step: "₹",
  signal: "⚠",
  note: "ⓘ",
};

const STATUS_TONE: Record<string, string> = {
  PASS: "text-emerald-700",
  OK: "text-emerald-700",
  FAIL: "text-rose-700",
  WARNING: "text-amber-700",
  REJECT: "text-rose-700",
  FINAL: "text-ink-900 font-semibold",
};

export function DecisionTree({ root }: { root: DecisionNode }) {
  return (
    <div className="rounded-2xl border border-ink-200 bg-white p-6 shadow-sm">
      <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-ink-500">
        Why was this decision reached?
      </div>
      <ul className="space-y-1 text-sm">
        <Node node={root} depth={0} defaultOpen />
      </ul>
    </div>
  );
}

function Node({
  node,
  depth,
  defaultOpen = false,
}: {
  node: DecisionNode;
  depth: number;
  defaultOpen?: boolean;
}) {
  const hasChildren = node.children && node.children.length > 0;
  const tone = node.status ? STATUS_TONE[node.status] ?? "" : "";
  return (
    <li>
      <details
        open={defaultOpen || depth < 1}
        className="group"
        style={{ paddingLeft: `${depth * 12}px` }}
      >
        <summary className="flex cursor-pointer items-center gap-2 rounded-md py-1 pr-2 hover:bg-ink-50">
          <span className="font-mono text-xs text-ink-400">
            {KIND_ICONS[node.kind] ?? "•"}
          </span>
          <span className={`flex-1 ${tone}`}>{node.label}</span>
          {node.status && (
            <span className={`text-[10px] uppercase tracking-wide ${tone}`}>
              {node.status}
            </span>
          )}
        </summary>
        {node.evidence && node.evidence.length > 0 ? (
          <div className="ml-6 mt-1 mb-1 space-y-1 text-xs text-ink-600">
            {node.evidence.map((e, i) => (
              <div key={i} className="rounded bg-ink-50 px-2 py-1">
                {e.snippet ? (
                  <span className="italic">&ldquo;{e.snippet}&rdquo;</span>
                ) : null}
                {e.source_file_id ? (
                  <span className="ml-2 font-mono text-[10px] text-ink-500">
                    file: {e.source_file_id}
                    {e.field_path ? ` · ${e.field_path}` : ""}
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
        {hasChildren ? (
          <ul className="space-y-1">
            {node.children.map((c, i) => (
              <Node key={i} node={c} depth={depth + 1} />
            ))}
          </ul>
        ) : null}
      </details>
    </li>
  );
}
