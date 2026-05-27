"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, type Member, type PolicySummary } from "@/lib/api";

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

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
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
        simulate_component_failure: simulateFailure,
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
        <label className="col-span-2 mt-2 inline-flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={simulateFailure}
            onChange={(e) => setSimulateFailure(e.target.checked)}
          />
          Simulate component failure (TC011)
        </label>
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
