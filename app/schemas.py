from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class GuidanceRequest(BaseModel):
    description: str = Field(..., min_length=1)
    category: Optional[str] = None


class RAGSourceItem(BaseModel):
    document_title: str
    filename: str
    page_number: int
    score: float
    excerpt: str


class GuidanceResponse(BaseModel):
    is_clear: bool
    clarity_message: Optional[str] = None
    identified_category: Optional[str] = None
    classification_method: Optional[str] = None
    recommended_department: Optional[str] = None
    jurisdiction_notes: Optional[str] = None
    jurisdiction_disclaimer: str
    match_confidence: Optional[str] = None
    has_verified_guidance: bool
    verified_guidance_message: Optional[str] = None
    ai_analysis: Optional[str] = None
    llm_provider: Optional[str] = None
    estimated_turnaround: Optional[str] = None
    procedure_steps: List[str] = []
    required_evidence: List[str] = []
    sources: List[RAGSourceItem] = []


class ComplaintCreate(BaseModel):
    category: str
    description: str
    location: str
    citizen_name: Optional[str] = "Concerned Citizen"
    citizen_email: Optional[str] = "citizen@civicfix.local"
    citizen_phone: Optional[str] = None


class ComplaintResponse(BaseModel):
    id: int
    complaint_no: str
    category: str
    description: str
    location: str
    image_path: Optional[str] = None
    status: str
    ai_summary: Optional[str] = None
    citizen_id: Optional[int] = None
    citizen_name: Optional[str] = None
    citizen_email: Optional[str] = None
    citizen_phone: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatusUpdateRequest(BaseModel):
    status: str


class LetterGenerateRequest(BaseModel):
    complaint_id: int
    citizen_name: Optional[str] = None
    citizen_phone: Optional[str] = None
    citizen_email: Optional[str] = None
    subject: Optional[str] = None
    recipient_department: Optional[str] = None
    letter_body: Optional[str] = None


class LLMConfigPayload(BaseModel):
    provider: str
    api_key: Optional[str] = ""
