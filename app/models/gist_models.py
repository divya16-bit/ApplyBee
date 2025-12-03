# models/gist_models.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class FieldItem(BaseModel):
    label: str
    type: Optional[str] = "text"
    options: Optional[List[str]] = None
    # optional UI metadata
    name: Optional[str] = None
    id: Optional[str] = None
    placeholder: Optional[str] = None

class GistRequest(BaseModel):
    parsed_resume: Dict[str, Any]
    job_description: Optional[str] = None
    job_url: Optional[str] = None
    fields: List[FieldItem] = []

class GistResponse(BaseModel):
    success: bool
    message: str
    answers: Dict[str, Any] = {}
