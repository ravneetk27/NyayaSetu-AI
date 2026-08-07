from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any

class ClassificationResult(BaseModel):
    category: Literal["POSH", "POCSO", "OTHER"]
    sub_category: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    minor_involved: bool
    rationale: str

class ExtractedFacts(BaseModel):
    complainant_name: Optional[str] = None
    complainant_age: Optional[str] = None
    respondent_name: Optional[str] = None
    respondent_designation: Optional[str] = None
    incident_date: Optional[str] = None
    incident_time: Optional[str] = None
    incident_location: Optional[str] = None
    nature_of_incident: str = "Unspecified incident description."
    witnesses: List[str] = Field(default_factory=list)
    evidence_description: List[str] = Field(default_factory=list)

class UIState(BaseModel):
    expand_draft_view: bool = False
    close_chat_tab: bool = False

class ExtractedEntities(BaseModel):
    complainant_name: str = "[Not Provided / Unspecified]"
    complainant_age: str = "[Not Provided / Unspecified]"
    respondent_name: str = "[Not Provided / Unspecified]"
    respondent_designation: str = "[Not Provided / Unspecified]"
    date_of_incident: str = "[Not Provided / Unspecified]"
    time_of_incident: str = "[Not Provided / Unspecified]"
    place_of_incident: str = "[Not Provided / Unspecified]"
    witnesses: str = "[None Specified]"
    evidence: str = "[None Provided]"

class AgentResponsePayload(BaseModel):
    is_posh_pocso_relevant: bool = True
    action_triggered: Literal["ADVISE", "GENERATE_DRAFT"] = "ADVISE"
    ui_state: UIState = Field(default_factory=UIState)
    advice_response: str = ""
    extracted_entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    formatted_draft: str = ""

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

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    action_triggered: Optional[Literal["ADVISE", "GENERATE_DRAFT"]] = "ADVISE"

class ChatResponse(BaseModel):
    reply: str
    quick_replies: List[str] = Field(default_factory=list)
    payload: Optional[AgentResponsePayload] = None

class AnalyzeComplaintRequest(BaseModel):
    raw_text: Optional[str] = None
    messages: Optional[List[ChatMessage]] = None
    action_triggered: Optional[Literal["ADVISE", "GENERATE_DRAFT"]] = "GENERATE_DRAFT"

class AnalyzeComplaintResponse(BaseModel):
    classification: ClassificationResult
    extracted_facts: ExtractedFacts
    draft: ComplaintDraft
    mandatory_report_alert: bool
    payload: Optional[AgentResponsePayload] = None

class IngestResponse(BaseModel):
    status: str
    processed_files: List[str]
    total_chunks: int
