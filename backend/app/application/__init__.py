"""Application layer: orchestration and use cases.

Coordinates domain objects to execute use cases (claim submission, eval
runs). Owns the LangGraph pipeline wiring, the per-step agents, the
trace recorder, and the abstract ports that infrastructure adapters
implement.
"""
