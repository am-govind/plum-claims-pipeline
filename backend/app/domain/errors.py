"""Typed errors and the single function that turns them into specific,
actionable user-facing messages.

Every error type interpolates the data the assignment requires:
- DocumentTypeMismatchError names what was uploaded and what is needed.
- UnreadableDocumentError names the specific file_id that must be reuploaded.
- PatientMismatchError names the two different patients found.
This is the heart of the "no generic errors" requirement.
"""

from __future__ import annotations

from typing import Any


class ClaimError(Exception):
    """Base for all typed claim-processing errors."""

    code: str = "CLAIM_ERROR"

    def __init__(self, message: str, *, evidence: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.evidence = evidence or {}


class DocumentVerificationError(ClaimError):
    code = "DOCUMENT_VERIFICATION_FAILED"


class DocumentTypeMismatchError(DocumentVerificationError):
    code = "DOCUMENT_TYPE_MISMATCH"

    def __init__(
        self,
        *,
        uploaded_types: list[str],
        required_types: list[str],
        missing_types: list[str],
        category: str,
    ) -> None:
        self.uploaded_types = uploaded_types
        self.required_types = required_types
        self.missing_types = missing_types
        self.category = category
        super().__init__(
            f"Wrong documents for {category}: uploaded {uploaded_types}, "
            f"required {required_types}, missing {missing_types}",
            evidence={
                "uploaded_types": uploaded_types,
                "required_types": required_types,
                "missing_types": missing_types,
                "category": category,
            },
        )


class UnreadableDocumentError(DocumentVerificationError):
    code = "DOCUMENT_UNREADABLE"

    def __init__(self, *, file_id: str, file_name: str | None, document_type: str) -> None:
        self.file_id = file_id
        self.file_name = file_name
        self.document_type = document_type
        super().__init__(
            f"Document {file_id} ({document_type}) is unreadable",
            evidence={"file_id": file_id, "file_name": file_name, "document_type": document_type},
        )


class PatientMismatchError(DocumentVerificationError):
    code = "PATIENT_MISMATCH"

    def __init__(self, *, names_by_file: dict[str, str]) -> None:
        self.names_by_file = names_by_file
        unique_names = sorted(set(names_by_file.values()))
        super().__init__(
            f"Documents belong to different patients: {unique_names}",
            evidence={"names_by_file": names_by_file, "unique_names": unique_names},
        )


def error_to_user_message(err: ClaimError) -> str:
    """Produce a specific, actionable user-facing message for any ClaimError.

    The whole point of this layer is to never return a generic error: the
    member must always know exactly what the problem is and what to do next.
    """
    if isinstance(err, DocumentTypeMismatchError):
        uploaded = ", ".join(err.uploaded_types) or "no recognised documents"
        required = ", ".join(err.required_types)
        missing = ", ".join(err.missing_types)
        return (
            f"Your {err.category.lower()} claim cannot be processed yet. "
            f"You uploaded: {uploaded}. "
            f"For a {err.category.lower()} claim we need: {required}. "
            f"Please upload the missing document(s): {missing}."
        )
    if isinstance(err, UnreadableDocumentError):
        label = err.file_name or err.file_id
        return (
            f"We couldn't read your {err.document_type.lower().replace('_', ' ')} ('{label}'). "
            f"The image is too blurry or low-contrast for our system to process. "
            f"Please re-upload a clearer photo or scan of this specific document. "
            f"All your other documents are fine — only re-upload file {err.file_id}."
        )
    if isinstance(err, PatientMismatchError):
        names = err.evidence.get("unique_names", [])
        details = ", ".join(
            f"{file_id}: {name}" for file_id, name in err.names_by_file.items()
        )
        return (
            f"The documents you uploaded belong to different patients ({', '.join(names)}). "
            f"We found: {details}. "
            f"All documents in a single claim must be for the same patient. "
            f"Please re-check and resubmit with documents that all belong to the same person."
        )
    return err.message
