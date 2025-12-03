# models/score_models.py
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

class ScoreRequest(BaseModel):
    parsed_resume: Dict[str, Any]
    job_description: Optional[str] = None
    job_url: Optional[str] = None

class ScoreResponse(BaseModel):
    success: bool
    detail: Optional[str] = None
    score: float = 0.0
    ats_score: float = 0.0
    responsibility_score: float = 0.0
    skills_score: float = 0.0
    common_skills: List[str] = []
    missing_skills: List[str] = []
    summary: Optional[str] = None
    years_experience_resume: Optional[float] = None
    years_experience_jd: Optional[Any] = None
    yoe_score: Optional[float] = None
    explanation: Optional[str] = None
    normalized_overlap: Optional[List[Any]] = []
    normalized_missing: Optional[List[Any]] = []
    direct_skill_score: Optional[float] = 0.0
    contextual_skill_score: Optional[float] = 0.0
    all_matched_skills: Optional[List[str]] = []
