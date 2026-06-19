from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Worker Key Schemas ---
class WorkerKeyCreate(BaseModel):
    name: str = Field(..., description="Name of the worker key")
    company_id: Optional[int] = None
    job_id: Optional[int] = None
    quota_limit: int = Field(..., ge=1, le=100000, description="Maximum number of CVs this key can process")
    expires_at: Optional[datetime] = None
    permissions: Dict[str, Any] = Field(default_factory=lambda: {"claim": True, "submit_results": True})

class WorkerKeyResponse(BaseModel):
    id: int
    name: str
    company_id: int
    job_id: Optional[int]
    key_prefix: str
    quota_limit: int
    quota_used: int
    quota_reserved: int
    quota_remaining: int
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    last_used_at: Optional[datetime]
    created_at: datetime
    permissions: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        from_attributes = True

class WorkerKeyCreateResponse(WorkerKeyResponse):
    api_key: str = Field(..., description="The plaintext API key, only returned once")

# --- Worker Auth & API Schemas ---
class WorkerAuthRequest(BaseModel):
    api_key: str
    device_name: Optional[str] = "unknown"
    worker_version: Optional[str] = "1.0.0"

class WorkerAuthResponse(BaseModel):
    access_token: str
    expires_in: int
    company_id: int
    allowed_jobs: List[int]
    quota_remaining: int
    permissions: Dict[str, Any] = Field(default_factory=dict)

class JobConfigResponse(BaseModel):
    job_id: int
    title: str
    description: str
    required_skills: List[str] = []
    nice_to_have_skills: List[str] = []
    hard_reject_criteria: List[str] = []
    scoring_weights: Dict[str, Any] = {}
    accept_threshold: int = 75
    review_threshold: int = 50
    reject_threshold: int = 30

class ClaimRequest(BaseModel):
    limit: int = Field(10, ge=1, le=50, description="Number of CVs to claim")

class ClaimItem(BaseModel):
    claim_id: int
    candidate_id: int
    candidate_action_id: Optional[int] = None
    cv_id: Optional[int]
    download_url: str
    file_name: str
    file_type: str

class ClaimResponse(BaseModel):
    items: List[ClaimItem]
    claim_expires_at: datetime

class AnalysisResultRequest(BaseModel):
    cv_id: Optional[int] = None
    candidate_id: int
    score: float = Field(..., ge=0, le=100)
    decision: str
    confidence: str
    summary: str
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    risk_flags: List[str] = []
    explanation: str
    worker_version: str
    engine_version: str
