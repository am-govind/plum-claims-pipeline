"""Composition root.

This is the *one* place in the system that knows how to construct every
collaborator and wire them into a working application. Higher layers
(`interfaces.http`, `eval.runner`) receive a fully-built `Container`
and use only the abstractions on it; lower layers (`domain`,
`application`) never reach back here.

If you're tempted to import from `app.composition` inside a domain or
application module, that's the smell — pass the dependency in instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.pipeline import (
    CompiledPipeline,
    PipelineDeps,
    build_pipeline,
)
from app.application.ports.claim_repository import ClaimRepository
from app.application.ports.event_bus import EventBus
from app.application.ports.llm import LLMProvider
from app.application.ports.policy_repository import PolicyRepository
from app.application.ports.rule_engine import RuleEngine
from app.config import Settings
from app.domain.policy.rules import DslRuleEngine
from app.domain.services.confidence import ConfidenceConfig
from app.infrastructure.events import (
    InMemoryEventBus,
    NotificationStubHandler,
    StructlogEventHandler,
)
from app.infrastructure.llm.factory import build_llm_provider
from app.infrastructure.persistence.claims_repository import SqlAlchemyClaimRepository
from app.infrastructure.persistence.database import Database
from app.infrastructure.policy.json_policy_repository import JsonPolicyRepository
from app.infrastructure.policy.json_rules_loader import (
    load_confidence_config,
    load_rules_data,
)


@dataclass(frozen=True)
class Container:
    """The fully-constructed object graph for one running application."""

    settings: Settings
    database: Database
    policy_repository: PolicyRepository
    rule_engine: RuleEngine
    confidence_config: ConfidenceConfig
    llm_provider: LLMProvider
    claim_repository: ClaimRepository
    pipeline: CompiledPipeline
    event_bus: EventBus


def compose(settings: Settings | None = None) -> Container:
    """Build the full object graph from a `Settings`.

    Pure construction: no IO except reading the policy and rules JSON
    files. Database connections are not opened here — call
    ``container.database.init()`` from the lifespan event when the
    application is ready to talk to its store.
    """
    settings = settings or Settings()

    database = Database(settings.database_url)
    policy_repository = JsonPolicyRepository(settings.policy_terms_path)
    policy = policy_repository.get_terms()

    rules_data = load_rules_data(settings.policy_rules_path)
    rule_engine = DslRuleEngine(rules_data=rules_data, policy=policy)
    confidence_config = load_confidence_config(settings.policy_rules_path)

    llm_provider = build_llm_provider(settings)
    claim_repository = SqlAlchemyClaimRepository(database)

    event_bus = InMemoryEventBus()
    event_bus.subscribe(StructlogEventHandler())
    event_bus.subscribe(NotificationStubHandler())

    pipeline = build_pipeline(
        PipelineDeps(
            policy=policy,
            rule_engine=rule_engine,
            llm_provider=llm_provider,
            confidence_config=confidence_config,
        )
    )

    return Container(
        settings=settings,
        database=database,
        policy_repository=policy_repository,
        rule_engine=rule_engine,
        confidence_config=confidence_config,
        llm_provider=llm_provider,
        claim_repository=claim_repository,
        pipeline=pipeline,
        event_bus=event_bus,
    )
