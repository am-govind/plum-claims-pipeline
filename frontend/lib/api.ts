export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${text ? `: ${text}` : ""}`);
  }
  return (await res.json()) as T;
}

export type Member = {
  member_id: string;
  name: string;
  relationship: string;
  join_date?: string;
  primary_member_id?: string;
};

export type PolicySummary = {
  policy_id: string;
  policy_name: string;
  insurer: string;
  categories: string[];
  document_requirements: Record<string, { required: string[]; optional: string[] }>;
  network_hospitals: string[];
  submission_rules: Record<string, unknown>;
  fraud_thresholds: Record<string, unknown>;
};

export type LineItemDecision = {
  description: string;
  submitted_amount: number;
  approved_amount: number;
  status: string;
  reason: string | null;
  rejection_code: string | null;
};

export type EvidenceLink = {
  source_file_id: string | null;
  field_path: string | null;
  snippet: string | null;
  page: number | null;
  bbox: [number, number, number, number] | null;
  confidence: number;
};

export type DecisionNode = {
  label: string;
  kind: "root" | "rule_group" | "rule" | "calc_step" | "signal" | "note";
  status: string | null;
  detail: Record<string, unknown>;
  evidence: EvidenceLink[];
  children: DecisionNode[];
};

export type CostBreakdown = {
  llm_calls: Array<{
    model: string;
    tokens_in: number;
    tokens_out: number;
    latency_ms: number;
    usd_estimate: number;
    file_id: string | null;
  }>;
  node_latencies: Array<{ node: string; latency_ms: number }>;
};

export type ConfidenceBreakdown = {
  final: number;
  weighted_sum: number;
  contradiction_penalty: number;
  degraded_penalty: number;
  alpha: number;
  beta: number;
  weights: Record<string, number>;
  per_component: Record<
    string,
    { weight: number; confidence: number; contribution: number }
  >;
};

export type Decision = {
  status: string;
  approved_amount: number;
  submitted_amount: number;
  rejection_reasons: string[];
  confidence: number;
  summary: string;
  user_message: string;
  notes: string[];
  breakdown: Record<string, unknown>;
  line_items: LineItemDecision[];
  requires_manual_review: boolean;
  degraded: boolean;
  failed_components: string[];
  explanation_tree: DecisionNode | null;
  cost: CostBreakdown | null;
  evidence_links: EvidenceLink[];
  confidence_breakdown: ConfidenceBreakdown | Record<string, never>;
};

export type TraceStep = {
  step: string;
  status: "OK" | "WARNING" | "ERROR" | "SKIPPED" | "EARLY_STOP";
  summary: string;
  evidence: Record<string, unknown>;
  confidence_delta: number;
  latency_ms: number;
  error: string | null;
  started_at: string;
};

export type ClaimStateResponse = {
  claim_id: string;
  state: {
    claim_id: string;
    input: Record<string, unknown>;
    extracted: Array<Record<string, unknown>>;
    findings: Array<Record<string, unknown>>;
    line_decisions: LineItemDecision[];
    fraud_signals: string[];
    trace: TraceStep[];
    degraded: boolean;
    failed_components: string[];
    confidence: number;
    early_stop: boolean;
    early_stop_reason: string | null;
    early_stop_user_message: string | null;
    decision: Decision | null;
  };
};

export type CaseMetrics = {
  total_latency_ms: number;
  node_latencies: Array<{ node: string; latency_ms: number }>;
  tokens_in: number;
  tokens_out: number;
  usd_estimate: number;
  extraction_confidences: number[];
  validation_issue_count: number;
  fired_rules: string[];
  contradictions: string[];
  deliberation_iterations: Record<string, number>;
};

export type ExtractedDocument = {
  file_id: string;
  document_type: string;
  quality: string;
  patient_name: string | null;
  doctor_name: string | null;
  doctor_registration: string | null;
  diagnosis: string | null;
  treatment: string | null;
  medicines: string[];
  tests_ordered: string[];
  hospital_name: string | null;
  bill_number: string | null;
  document_date: string | null;
  line_items: Array<{ description: string; amount: number }>;
  total_amount: number | null;
  extraction_confidence: number;
  validation_issues: string[];
  raw: Record<string, unknown>;
};

export type ExtractPreviewResponse = {
  ok: boolean;
  extracted: ExtractedDocument | null;
  usage: {
    model: string;
    tokens_in: number;
    tokens_out: number;
    latency_ms: number;
    usd_estimate: number;
    file_id: string | null;
  } | null;
  validation_issues: string[];
  reason: string | null;
  message: string | null;
};

export type EvalRunResponse = {
  total: number;
  passed: number;
  failed: number;
  results: Array<{
    case_id: string;
    case_name: string;
    passed: boolean;
    issues: string[];
    expected: Record<string, unknown>;
    decision: Decision | null;
    early_stop: boolean;
    early_stop_reason: string | null;
    early_stop_user_message: string | null;
    trace: TraceStep[];
    system_must_results: Array<{ requirement: string; satisfied: boolean }>;
    degraded: boolean;
    failed_components: string[];
    confidence: number;
    metrics?: CaseMetrics;
  }>;
};
