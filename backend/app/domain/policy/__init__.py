"""Policy domain: `PolicyTerms` aggregate and pure rule helpers.

Rule loading and IO live in `app.infrastructure.policy`. Consumers
should accept a `PolicyTerms` (or a `DslRuleEngine`) via constructor
injection rather than reach for module-level loaders.
"""

from app.domain.policy.coverage import (
    apply_financial_calculation,
    category_config,
    is_category_covered,
    line_item_excluded_reason,
)
from app.domain.policy.exclusions import diagnosis_excluded_reason
from app.domain.policy.pre_auth import pre_auth_violation
from app.domain.policy.terms import PolicyTerms
from app.domain.policy.waiting_periods import waiting_period_violation

__all__ = [
    "PolicyTerms",
    "apply_financial_calculation",
    "category_config",
    "diagnosis_excluded_reason",
    "is_category_covered",
    "line_item_excluded_reason",
    "pre_auth_violation",
    "waiting_period_violation",
]
