from typing import Literal
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)


class Evidence(BaseModel):
    title: str
    url: str
    snippet: str
    quality: Literal["High", "Medium", "Low"] = "Medium"


class ClaimCheck(BaseModel):
    claim: str
    status: Literal["Supported", "Contradicted", "Uncertain"]
    reasoning: str


class AnalyzeResponse(BaseModel):
    question: str
    initial_answer: str
    research: str
    fact_check: list[ClaimCheck]
    critic: str
    confidence_score: int
    trust_level: Literal["High", "Medium", "Low"]
    verification_status: str
    detected_issues: list[str]
    final_answer: str
    evidence: list[Evidence]
    agent_analysis: dict[str, str]
    demo_mode: bool
