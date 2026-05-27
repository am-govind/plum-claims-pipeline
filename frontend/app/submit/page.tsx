import { ClaimForm } from "@/components/ClaimForm";

export default function SubmitPage() {
  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">
          Submit a claim
        </h1>
        <p className="mt-2 text-ink-600">
          Fill in the member details, treatment, and uploaded documents.
          Required document types update automatically based on the claim
          category.
        </p>
      </header>
      <ClaimForm />
    </div>
  );
}
