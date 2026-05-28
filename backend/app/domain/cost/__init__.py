"""Cost + latency aggregation across the pipeline.

Every LLM call returns an ``LLMUsage``; the orchestrator sums them onto
``state.cost`` so the decision card can show "this decision used X
tokens / $Y / Z seconds". MockProvider returns realistic-but-fake usage so
the eval suite has cost data without burning tokens.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Public per-million-token pricing (USD); updated 2025-11. Conservative
# estimates kept here so the demo numbers are believable but never wrong
# enough to mislead a reviewer. Real ops would read these from a config
# table and version them.
MODEL_PRICING_USD_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "mock": (0.0, 0.0),
}


def estimate_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Return USD cost using the public per-1M-token rate table."""
    rates = MODEL_PRICING_USD_PER_M_TOKENS.get(
        model, MODEL_PRICING_USD_PER_M_TOKENS["mock"]
    )
    in_rate, out_rate = rates
    return round((tokens_in / 1_000_000) * in_rate + (tokens_out / 1_000_000) * out_rate, 6)


class LLMUsage(BaseModel):
    """One LLM call's token + latency + cost record."""

    model: str = "unknown"
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    usd_estimate: float = 0.0
    file_id: str | None = None


class NodeLatency(BaseModel):
    """Latency record for a single pipeline node."""

    node: str
    latency_ms: int


class CostBreakdown(BaseModel):
    """Pipeline-wide cost + latency aggregation."""

    llm_calls: list[LLMUsage] = Field(default_factory=list)
    node_latencies: list[NodeLatency] = Field(default_factory=list)

    @property
    def total_tokens_in(self) -> int:
        return sum(c.tokens_in for c in self.llm_calls)

    @property
    def total_tokens_out(self) -> int:
        return sum(c.tokens_out for c in self.llm_calls)

    @property
    def total_tokens(self) -> int:
        return self.total_tokens_in + self.total_tokens_out

    @property
    def total_usd(self) -> float:
        return round(sum(c.usd_estimate for c in self.llm_calls), 6)

    @property
    def total_latency_ms(self) -> int:
        return sum(n.latency_ms for n in self.node_latencies)

    def add_llm(self, usage: LLMUsage) -> None:
        self.llm_calls.append(usage)

    def add_node(self, node: str, latency_ms: int) -> None:
        self.node_latencies.append(NodeLatency(node=node, latency_ms=latency_ms))
