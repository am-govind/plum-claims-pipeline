"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  apiFetch,
  type ExtractPreviewResponse,
  type Member,
  type PolicySummary,
} from "@/lib/api";
import { IS_DEV_MODE } from "@/lib/devMode";

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

const DOCUMENT_TYPES = [
  "PRESCRIPTION",
  "HOSPITAL_BILL",
  "PHARMACY_BILL",
  "LAB_REPORT",
  "DIAGNOSTIC_REPORT",
  "DISCHARGE_SUMMARY",
  "DENTAL_REPORT",
  "UNKNOWN",
] as const;

const QUALITIES = ["GOOD", "ACCEPTABLE", "POOR", "UNREADABLE"] as const;

type DocumentDraft = {
  file_id: string;
  file_name: string;
  actual_type: (typeof DOCUMENT_TYPES)[number];
  quality: (typeof QUALITIES)[number];
  patient_name_on_doc: string;
  total_amount: string;
  diagnosis: string;
  doctor_name: string;
  doctor_registration: string;
  hospital_name: string;
  bytes_b64?: string;
  mime_type?: string;
  extraction_confidence?: number;
  extracted_by?: string;
  extracting?: boolean;
  extract_error?: string | null;
};

function emptyDoc(idx: number): DocumentDraft {
  return {
    file_id: `F${String(idx).padStart(3, "0")}`,
    file_name: `document_${idx}.jpg`,
    actual_type: "PRESCRIPTION",
    quality: "GOOD",
    patient_name_on_doc: "",
    total_amount: "",
    diagnosis: "",
    doctor_name: "",
    doctor_registration: "",
    hospital_name: "",
  };
}

function isKnownDocType(t: string): boolean {
  return (DOCUMENT_TYPES as readonly string[]).includes(t);
}

function isKnownQuality(q: string): boolean {
  return (QUALITIES as readonly string[]).includes(q);
}

function stripDataUrlPrefix(dataUrl: string): string {
  const comma = dataUrl.indexOf(",");
  return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
}

function readFileAsBase64(
  file: File
): Promise<{ bytes_b64: string; mime_type: string }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("File read failed"));
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("FileReader did not return a string"));
        return;
      }
      resolve({
        bytes_b64: stripDataUrlPrefix(result),
        mime_type: file.type || "application/octet-stream",
      });
    };
    reader.readAsDataURL(file);
  });
}

export function ClaimForm() {
  const router = useRouter();
  const [members, setMembers] = useState<Member[]>([]);
  const [policy, setPolicy] = useState<PolicySummary | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [memberId, setMemberId] = useState("EMP001");
  const [category, setCategory] = useState("CONSULTATION");
  const [treatmentDate, setTreatmentDate] = useState("2024-11-01");
  const [claimedAmount, setClaimedAmount] = useState("1500");
  const [hospitalName, setHospitalName] = useState("");
  const [ytdAmount, setYtdAmount] = useState("0");
  const [simulateFailure, setSimulateFailure] = useState(false);
  const [docs, setDocs] = useState<DocumentDraft[]>([
    emptyDoc(1),
    emptyDoc(2),
  ]);

  useEffect(() => {
    Promise.all([
      apiFetch<Member[]>("/api/members"),
      apiFetch<PolicySummary>("/api/policy"),
    ])
      .then(([m, p]) => {
        setMembers(m);
        setPolicy(p);
      })
      .catch((e) => setError(`Failed to load policy data: ${e.message}`));
  }, []);

  const requiredTypes = useMemo(() => {
    if (!policy) return [];
    return policy.document_requirements[category]?.required ?? [];
  }, [category, policy]);

  function updateDoc(i: number, patch: Partial<DocumentDraft>) {
    setDocs((d) => d.map((doc, j) => (j === i ? { ...doc, ...patch } : doc)));
  }

  function addDoc() {
    setDocs((d) => [...d, emptyDoc(d.length + 1)]);
  }

  function removeDoc(i: number) {
    setDocs((d) => d.filter((_, j) => j !== i));
  }

  function clearUpload(i: number) {
    updateDoc(i, {
      bytes_b64: undefined,
      mime_type: undefined,
      extraction_confidence: undefined,
      extracted_by: undefined,
      extract_error: null,
    });
  }

  async function onPickFile(i: number, file: File | null) {
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      updateDoc(i, {
        extract_error: `File is ${(file.size / 1024 / 1024).toFixed(1)} MB. Max upload size is 10 MB.`,
      });
      return;
    }
    let bytes_b64: string;
    let mime_type: string;
    try {
      ({ bytes_b64, mime_type } = await readFileAsBase64(file));
    } catch (err) {
      updateDoc(i, {
        extract_error:
          err instanceof Error ? err.message : "Could not read selected file",
      });
      return;
    }
    updateDoc(i, {
      file_name: file.name,
      bytes_b64,
      mime_type,
      extracting: true,
      extract_error: null,
    });
    const currentDoc = docs[i];
    try {
      const res = await apiFetch<ExtractPreviewResponse>(
        "/api/claims/extract-preview",
        {
          method: "POST",
          body: JSON.stringify({
            document: {
              file_id: currentDoc.file_id,
              file_name: file.name,
              actual_type: currentDoc.actual_type,
              quality: currentDoc.quality,
              patient_name_on_doc: currentDoc.patient_name_on_doc || undefined,
              bytes_b64,
              mime_type,
            },
            hint_category: category,
          }),
        }
      );
      if (!res.ok || !res.extracted) {
        updateDoc(i, {
          extracting: false,
          extract_error:
            res.message ?? res.reason ?? "Extraction returned no data",
        });
        return;
      }
      const ed = res.extracted;
      updateDoc(i, {
        extracting: false,
        extract_error: null,
        actual_type: isKnownDocType(ed.document_type)
          ? (ed.document_type as DocumentDraft["actual_type"])
          : currentDoc.actual_type,
        quality: isKnownQuality(ed.quality)
          ? (ed.quality as DocumentDraft["quality"])
          : currentDoc.quality,
        patient_name_on_doc: ed.patient_name ?? currentDoc.patient_name_on_doc,
        diagnosis: ed.diagnosis ?? currentDoc.diagnosis,
        doctor_name: ed.doctor_name ?? currentDoc.doctor_name,
        doctor_registration:
          ed.doctor_registration ?? currentDoc.doctor_registration,
        hospital_name: ed.hospital_name ?? currentDoc.hospital_name,
        total_amount:
          ed.total_amount != null
            ? String(ed.total_amount)
            : currentDoc.total_amount,
        extraction_confidence: ed.extraction_confidence,
        extracted_by: res.usage?.model ?? undefined,
      });
    } catch (err) {
      updateDoc(i, {
        extracting: false,
        extract_error:
          err instanceof Error ? err.message : "Extraction request failed",
      });
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      // We deliberately do NOT send `bytes_b64`/`mime_type` here. Those were
      // already extracted via /api/claims/extract-preview (or supplied as
      // typed values) and the result has been folded back into the form's
      // text fields. Re-sending bytes would trigger a second Gemini call at
      // pipeline-time and discard any corrections the user just made.
      const documents = docs.map((d) => ({
        file_id: d.file_id,
        file_name: d.file_name,
        actual_type: d.actual_type,
        quality: d.quality,
        patient_name_on_doc: d.patient_name_on_doc || undefined,
        content: {
          patient_name: d.patient_name_on_doc || undefined,
          doctor_name: d.doctor_name || undefined,
          doctor_registration: d.doctor_registration || undefined,
          diagnosis: d.diagnosis || undefined,
          hospital_name: d.hospital_name || undefined,
          total: d.total_amount ? Number(d.total_amount) : undefined,
        },
      }));
      const payload = {
        member_id: memberId,
        policy_id: policy?.policy_id ?? "PLUM_GHI_2024",
        claim_category: category,
        treatment_date: treatmentDate,
        claimed_amount: Number(claimedAmount),
        hospital_name: hospitalName || undefined,
        ytd_claims_amount: Number(ytdAmount || 0),
        // Belt-and-suspenders: even if `simulateFailure` somehow ends up
        // true in a production build (e.g. stale React state from an
        // earlier dev-mode session), we never propagate it to the API.
        simulate_component_failure: IS_DEV_MODE ? simulateFailure : false,
        documents,
      };
      const res = await apiFetch<{ claim_id: string }>("/api/claims", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      router.push(`/claims/${res.claim_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <section className="grid gap-6 rounded-2xl border border-ink-200 bg-white p-6 md:grid-cols-2">
        <Field label="Member">
          <select
            value={memberId}
            onChange={(e) => setMemberId(e.target.value)}
            className="input"
          >
            {members.map((m) => (
              <option key={m.member_id} value={m.member_id}>
                {m.member_id} — {m.name} ({m.relationship})
              </option>
            ))}
          </select>
        </Field>
        <Field label="Claim category">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="input"
          >
            {(policy?.categories ?? ["consultation"]).map((c) => (
              <option key={c} value={c.toUpperCase()}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Treatment date">
          <input
            type="date"
            value={treatmentDate}
            onChange={(e) => setTreatmentDate(e.target.value)}
            className="input"
          />
        </Field>
        <Field label="Claimed amount (INR)">
          <input
            type="number"
            value={claimedAmount}
            onChange={(e) => setClaimedAmount(e.target.value)}
            className="input"
            min={0}
            step="0.01"
            required
          />
        </Field>
        <Field label="Hospital / clinic name (optional)">
          <input
            type="text"
            value={hospitalName}
            onChange={(e) => setHospitalName(e.target.value)}
            className="input"
            placeholder="e.g. Apollo Hospitals"
          />
        </Field>
        <Field label="YTD claims amount">
          <input
            type="number"
            value={ytdAmount}
            onChange={(e) => setYtdAmount(e.target.value)}
            className="input"
            min={0}
            step="0.01"
          />
        </Field>
        {IS_DEV_MODE ? (
          <label className="col-span-2 mt-2 inline-flex items-center gap-2 text-sm text-ink-500">
            <input
              type="checkbox"
              checked={simulateFailure}
              onChange={(e) => setSimulateFailure(e.target.checked)}
            />
            <span>
              Dev-only: simulate component failure (TC011) — hidden in
              production builds via <code>NEXT_PUBLIC_DEV_MODE=false</code>
            </span>
          </label>
        ) : null}
        {requiredTypes.length > 0 ? (
          <div className="col-span-2 rounded-lg bg-ink-50 p-3 text-xs text-ink-600">
            <span className="font-semibold">Required for {category}:</span>{" "}
            {requiredTypes.join(", ")}
          </div>
        ) : null}
      </section>

      <section className="rounded-2xl border border-ink-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Documents</h3>
          <button type="button" onClick={addDoc} className="btn-secondary">
            + Add document
          </button>
        </div>
        <div className="mt-4 space-y-4">
          {docs.map((d, i) => (
            <div
              key={d.file_id}
              className="rounded-lg border border-ink-200 p-4"
            >
              <div className="flex items-center justify-between">
                <div className="font-mono text-sm">{d.file_id}</div>
                <button
                  type="button"
                  onClick={() => removeDoc(i)}
                  className="text-xs text-rose-600 hover:underline"
                >
                  Remove
                </button>
              </div>
              <div className="mt-3 rounded-lg border border-dashed border-ink-300 bg-ink-50 p-3">
                <label className="flex flex-wrap items-center gap-3 text-sm">
                  <span className="font-medium text-ink-700">
                    Upload document
                  </span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,application/pdf"
                    onChange={(e) =>
                      onPickFile(i, e.target.files?.[0] ?? null)
                    }
                    className="text-xs"
                    disabled={d.extracting}
                  />
                  {d.bytes_b64 ? (
                    <button
                      type="button"
                      onClick={() => clearUpload(i)}
                      className="text-xs text-rose-600 hover:underline"
                    >
                      Clear upload
                    </button>
                  ) : null}
                </label>
                {d.extracting ? (
                  <div className="mt-2 text-xs text-ink-600">
                    Extracting with {policy ? "configured provider" : "LLM"}…
                  </div>
                ) : null}
                {d.extract_error ? (
                  <div className="mt-2 rounded border border-rose-200 bg-rose-50 px-2 py-1 text-xs text-rose-700">
                    {d.extract_error}
                  </div>
                ) : null}
                {d.bytes_b64 &&
                !d.extracting &&
                !d.extract_error &&
                d.extraction_confidence != null ? (
                  <div className="mt-2 inline-flex items-center gap-2 rounded border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs text-emerald-800">
                    <span>
                      Auto-filled
                      {d.extracted_by ? ` by ${d.extracted_by}` : ""}
                    </span>
                    <span className="font-mono">
                      confidence {Math.round(d.extraction_confidence * 100)}%
                    </span>
                    <span className="text-emerald-700">
                      · review and edit any field below before submitting
                    </span>
                  </div>
                ) : null}
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <Field label="File name">
                  <input
                    type="text"
                    value={d.file_name}
                    onChange={(e) =>
                      updateDoc(i, { file_name: e.target.value })
                    }
                    className="input"
                  />
                </Field>
                <Field label="Document type">
                  <select
                    value={d.actual_type}
                    onChange={(e) =>
                      updateDoc(i, {
                        actual_type: e.target
                          .value as DocumentDraft["actual_type"],
                      })
                    }
                    className="input"
                  >
                    {DOCUMENT_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Quality">
                  <select
                    value={d.quality}
                    onChange={(e) =>
                      updateDoc(i, {
                        quality: e.target.value as DocumentDraft["quality"],
                      })
                    }
                    className="input"
                  >
                    {QUALITIES.map((q) => (
                      <option key={q} value={q}>
                        {q}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Patient name on document">
                  <input
                    type="text"
                    value={d.patient_name_on_doc}
                    onChange={(e) =>
                      updateDoc(i, { patient_name_on_doc: e.target.value })
                    }
                    className="input"
                  />
                </Field>
                <Field label="Diagnosis (Rx only)">
                  <input
                    type="text"
                    value={d.diagnosis}
                    onChange={(e) =>
                      updateDoc(i, { diagnosis: e.target.value })
                    }
                    className="input"
                  />
                </Field>
                <Field label="Doctor name (Rx only)">
                  <input
                    type="text"
                    value={d.doctor_name}
                    onChange={(e) =>
                      updateDoc(i, { doctor_name: e.target.value })
                    }
                    className="input"
                  />
                </Field>
                <Field label="Doctor registration">
                  <input
                    type="text"
                    value={d.doctor_registration}
                    onChange={(e) =>
                      updateDoc(i, { doctor_registration: e.target.value })
                    }
                    className="input"
                    placeholder="e.g. KA/45678/2015"
                  />
                </Field>
                <Field label="Hospital name (bill only)">
                  <input
                    type="text"
                    value={d.hospital_name}
                    onChange={(e) =>
                      updateDoc(i, { hospital_name: e.target.value })
                    }
                    className="input"
                  />
                </Field>
                <Field label="Total amount (bill only)">
                  <input
                    type="number"
                    value={d.total_amount}
                    onChange={(e) =>
                      updateDoc(i, { total_amount: e.target.value })
                    }
                    className="input"
                    step="0.01"
                  />
                </Field>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={submitting}
          className="btn-primary disabled:opacity-50"
        >
          {submitting ? "Processing…" : "Submit claim"}
        </button>
      </div>

      <style jsx global>{`
        .input {
          width: 100%;
          border-radius: 0.5rem;
          border: 1px solid rgb(226 232 240);
          background: white;
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          color: rgb(15 23 42);
        }
        .input:focus {
          outline: none;
          border-color: rgb(15 23 42);
          box-shadow: 0 0 0 1px rgb(15 23 42);
        }
        .btn-primary {
          background: rgb(15 23 42);
          color: white;
          padding: 0.625rem 1.25rem;
          border-radius: 0.5rem;
          font-size: 0.875rem;
          font-weight: 500;
        }
        .btn-primary:hover {
          background: rgb(30 41 59);
        }
        .btn-secondary {
          border: 1px solid rgb(226 232 240);
          background: white;
          color: rgb(51 65 85);
          padding: 0.5rem 1rem;
          border-radius: 0.5rem;
          font-size: 0.75rem;
          font-weight: 500;
        }
      `}</style>
    </form>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-600">
        {label}
      </span>
      {children}
    </label>
  );
}
