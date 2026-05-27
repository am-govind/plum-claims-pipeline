"""`PolicyTerms` aggregate: the parsed policy_terms.json snapshot.

Pure-domain value object. Construct one explicitly (or via the
`JsonPolicyRepository` adapter); pass it down where it is needed.
There are no module-level loaders here any more — file IO lives in
`app.infrastructure.policy`.
"""

from __future__ import annotations

from datetime import date as DateType
from datetime import datetime
from typing import Any


class PolicyTerms:
    """Convenience wrapper around the parsed policy_terms.json dict."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw
        self._members_by_id: dict[str, dict[str, Any]] = {
            m["member_id"]: m for m in raw.get("members", [])
        }

    @property
    def policy_id(self) -> str:
        return self.raw["policy_id"]

    @property
    def coverage(self) -> dict[str, Any]:
        return self.raw["coverage"]

    @property
    def opd_categories(self) -> dict[str, Any]:
        return self.raw["opd_categories"]

    @property
    def waiting_periods(self) -> dict[str, Any]:
        return self.raw["waiting_periods"]

    @property
    def exclusions(self) -> dict[str, Any]:
        return self.raw["exclusions"]

    @property
    def pre_authorization(self) -> dict[str, Any]:
        return self.raw["pre_authorization"]

    @property
    def network_hospitals(self) -> list[str]:
        return self.raw.get("network_hospitals", [])

    @property
    def submission_rules(self) -> dict[str, Any]:
        return self.raw["submission_rules"]

    @property
    def document_requirements(self) -> dict[str, Any]:
        return self.raw["document_requirements"]

    @property
    def fraud_thresholds(self) -> dict[str, Any]:
        return self.raw["fraud_thresholds"]

    def get_member(self, member_id: str) -> dict[str, Any] | None:
        return self._members_by_id.get(member_id)

    def member_join_date(self, member_id: str) -> DateType | None:
        m = self.get_member(member_id)
        if not m:
            return None
        primary = m.get("primary_member_id")
        if primary and primary in self._members_by_id:
            join = self._members_by_id[primary].get("join_date")
        else:
            join = m.get("join_date")
        return _parse_date(join) if join else None

    def is_network_hospital(self, name: str | None) -> bool:
        """Match input hospital name against the policy's network list.

        Real-world inputs vary: 'Apollo Hospitals' (canonical) vs 'apollo
        hospital, bengaluru' (with city). We normalise by stripping common
        facility suffixes and comparing on the leading brand tokens.
        """
        if not name:
            return False
        n_brand = _brand_root(name)
        for h in self.network_hospitals:
            h_brand = _brand_root(h)
            if not h_brand:
                continue
            if h_brand == n_brand or n_brand.startswith(h_brand) or h_brand in n_brand:
                return True
        return False


def _parse_date(s: str | DateType) -> DateType:
    if isinstance(s, DateType):
        return s
    return datetime.strptime(s, "%Y-%m-%d").date()


def _brand_root(s: str) -> str:
    """Return the brand part of a hospital name in lower-case form, e.g.
    'Apollo Hospitals' -> 'apollo', 'apollo hospital, bengaluru' -> 'apollo'.
    """
    cleaned = s.lower().split(",")[0].strip()
    for suffix in (" hospitals", " hospital", " healthcare", " health"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
            break
    return cleaned
