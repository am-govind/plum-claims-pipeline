"""Pipeline agents.

Each agent is a small object with a single ``run(state) -> state`` method.
The orchestrator (graph/pipeline.py) wraps every call in a try/except so
one failing component doesn't take the whole claim down (TC011).
"""

from app.agents.base import BaseAgent
from app.agents.decision_synthesizer import DecisionSynthesizerAgent
from app.agents.document_verification import DocumentVerificationAgent
from app.agents.extraction import ExtractionAgent
from app.agents.financial_calculation import FinancialCalculationAgent
from app.agents.fraud_detection import FraudDetectionAgent
from app.agents.intake import IntakeAgent
from app.agents.policy_adjudication import PolicyAdjudicationAgent

__all__ = [
    "BaseAgent",
    "DecisionSynthesizerAgent",
    "DocumentVerificationAgent",
    "ExtractionAgent",
    "FinancialCalculationAgent",
    "FraudDetectionAgent",
    "IntakeAgent",
    "PolicyAdjudicationAgent",
]
