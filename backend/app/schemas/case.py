from pydantic import BaseModel, Field
from typing import Literal, Optional, List

class ClassificationResult(BaseModel):
    category: Literal["POSH", "POCSO", "OTHER"]
    sub_category: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    minor_involved: bool
    rationale: str

class ExtractedFacts(BaseModel):
    complainant_name: Optional[str] = None
    respondent_name: Optional[str] = None
    incident_date: Optional[str] = None
    incident_location: Optional[str] = None
    nature_of_incident: str
    witnesses: List[str] = Field(default_factory=list)
    evidence_description: List[str] = Field(default_factory=list)

class RetrievedContext(BaseModel):
    source: str
    text_snippet: str
    relevance_score: float

class ComplaintDraft(BaseModel):
    category: Literal["POSH", "POCSO", "OTHER"]
    addressed_to: str
    draft_text: str
    disclaimer: str
    citations: List[RetrievedContext] = Field(default_factory=list)

class AnalyzeComplaintRequest(BaseModel):
    raw_text: str

class AnalyzeComplaintResponse(BaseModel):
    classification: ClassificationResult
    extracted_facts: ExtractedFacts
    draft: ComplaintDraft
    mandatory_report_alert: bool

class IngestResponse(BaseModel):
    status: str
    processed_files: List[str]
    total_chunks: int
